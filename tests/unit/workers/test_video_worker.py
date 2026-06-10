import pytest

from app.core.constants import VideoJobStatus
from app.repositories.kvrocks.queue_repository import InMemoryVideoQueueRepository
from app.schemas.video import VideoDetectRequest
from app.services.queue_service import QueueService
from app.services.video_processing_service import ProcessingFailure, VideoJobProcessingError
from app.workers.video_worker import VideoQueueWorker


def request() -> VideoDetectRequest:
    return VideoDetectRequest(
        job_id="job",
        video_id="video",
        publisher_user_id="user",
        source_video_uri="https://example.com/video.mp4",
        source_object_version="",
        policy_version="nsfw_policy_v1",
        trace_id="trace",
    )


class SuccessfulProcessor:
    def __init__(self) -> None:
        self.jobs: list[str] = []

    async def process(self, job) -> None:  # type: ignore[no-untyped-def]
        self.jobs.append(job.job_id)


class FailingProcessor:
    def __init__(self, failure: ProcessingFailure) -> None:
        self.failure = failure

    async def process(self, job) -> None:  # type: ignore[no-untyped-def]
        del job
        raise VideoJobProcessingError(self.failure)


async def build_worker(test_settings, processor):  # type: ignore[no-untyped-def]
    settings = test_settings.model_copy(update={"queue_read_count": 1, "queue_block_ms": 0})
    queue_repository = InMemoryVideoQueueRepository()
    queue_service = QueueService(queue_repository)
    await queue_repository.enqueue_video_job(request())
    worker = VideoQueueWorker(
        settings=settings,
        queue_service=queue_service,
        processor=processor,
        consumer_name="test-consumer",
    )
    return worker, queue_repository


@pytest.mark.asyncio
async def test_worker_acks_successful_job(test_settings) -> None:  # type: ignore[no-untyped-def]
    processor = SuccessfulProcessor()
    worker, queue_repository = await build_worker(test_settings, processor)

    processed = await worker.run_once()
    next_batch = await queue_repository.read_video_job_messages(
        consumer_name="test-consumer",
        count=1,
        block_ms=0,
    )

    assert processed == 1
    assert processor.jobs == ["job"]
    assert next_batch == []
    assert queue_repository.dlq == []


@pytest.mark.asyncio
async def test_worker_requeues_retryable_failure(test_settings) -> None:  # type: ignore[no-untyped-def]
    failure = ProcessingFailure(
        status=VideoJobStatus.FAILED_RETRYABLE,
        error_code="http_503",
        error_message="unavailable",
        retryable=True,
    )
    worker, queue_repository = await build_worker(test_settings, FailingProcessor(failure))

    processed = await worker.run_once()
    next_batch = await queue_repository.read_video_job_messages(
        consumer_name="test-consumer",
        count=1,
        block_ms=0,
    )

    assert processed == 1
    assert [message.job_id for message in next_batch] == ["job"]
    assert len(queue_repository.queue) == 2
    assert queue_repository.dlq == []


@pytest.mark.asyncio
async def test_worker_moves_terminal_failure_to_dlq(test_settings) -> None:  # type: ignore[no-untyped-def]
    failure = ProcessingFailure(
        status=VideoJobStatus.FAILED_TERMINAL,
        error_code="video_too_large",
        error_message="too large",
        retryable=False,
    )
    worker, queue_repository = await build_worker(test_settings, FailingProcessor(failure))

    processed = await worker.run_once()
    next_batch = await queue_repository.read_video_job_messages(
        consumer_name="test-consumer",
        count=1,
        block_ms=0,
    )

    assert processed == 1
    assert next_batch == []
    assert queue_repository.dlq[0]["job_id"] == "job"
    assert queue_repository.dlq[0]["error_code"] == "video_too_large"
