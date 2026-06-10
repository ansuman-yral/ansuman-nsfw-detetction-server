from dataclasses import replace
from pathlib import Path

import httpx
import pytest

from app.core.constants import VideoJobStatus
from app.models.frame_result import FrameModerationResult
from app.models.video_job import VideoJob
from app.models.video_metadata import VideoMetadata
from app.repositories.kvrocks.queue_repository import InMemoryVideoQueueRepository
from app.schemas.video import VideoDetectRequest
from app.services.aggregation_service import AggregationService
from app.services.frame_extraction_service import ExtractedFrame, job_temp_dir
from app.services.queue_service import QueueService
from app.services.video_processing_service import VideoJobProcessingError, VideoJobProcessor, classify_processing_error


def request(*, source_video_uri: str = "https://example.com/video.mp4") -> VideoDetectRequest:
    return VideoDetectRequest(
        job_id="job",
        video_id="video",
        publisher_user_id="user",
        source_video_uri=source_video_uri,
        source_object_version="",
        policy_version="nsfw_policy_v1",
        trace_id="trace",
    )


def categories(**overrides: int) -> dict[str, int]:
    base = {
        "safe": 0,
        "suggestive": 0,
        "nudity": 0,
        "porn": 0,
        "gore": 0,
        "violence": 0,
        "self_harm": 0,
        "hate_or_extremism": 0,
        "drugs": 0,
        "unknown": 0,
        "sexual_minor_content": 0,
    }
    base.update(overrides)
    return base


class FakeJobStateRepository:
    def __init__(self) -> None:
        self.jobs: dict[str, VideoJob] = {}
        self.processing: list[str] = []
        self.failed: list[tuple[str, VideoJobStatus, str]] = []

    async def get_by_job_id(self, job_id: str) -> VideoJob | None:
        return self.jobs.get(job_id)

    async def mark_processing(self, job: VideoJob) -> None:
        self.processing.append(job.job_id)
        self.jobs[job.job_id] = replace(job, status=VideoJobStatus.PROCESSING)

    async def mark_failed(
        self,
        job_id: str,
        *,
        status: VideoJobStatus,
        error_code: str,
        error_message: str,
    ) -> None:
        del error_message
        self.failed.append((job_id, status, error_code))
        if job_id in self.jobs:
            self.jobs[job_id] = replace(self.jobs[job_id], status=status, last_error_code=error_code)


class FakeFrameExtractionService:
    def __init__(self, temp_root: Path) -> None:
        self._temp_root = temp_root

    async def prepare_job_dir(self, job_id: str) -> Path:
        directory = self._temp_root / job_id
        (directory / "frames").mkdir(parents=True)
        return directory

    async def probe(self, *, job_id: str, video_id: str, source_path: Path) -> VideoMetadata:
        assert source_path.exists()
        return VideoMetadata(
            job_id=job_id,
            video_id=video_id,
            duration_seconds=2.0,
            width=320,
            height=180,
            fps=1.0,
            codec_name="h264",
            has_video_stream=True,
            frames_extracted=0,
        )

    async def extract_frames(self, source_path: Path, frames_dir: Path) -> list[ExtractedFrame]:
        assert source_path.exists()
        frame_path = frames_dir / "frame-000001.jpg"
        frame_path.write_bytes(b"frame")
        return [ExtractedFrame(frame_index=0, timestamp_seconds=0.0, path=frame_path)]


class FakeGpuService:
    async def moderate_frame_batch(self, frames: list[ExtractedFrame]) -> list[FrameModerationResult]:
        return [
            FrameModerationResult(
                frame_index=frame.frame_index,
                frame_timestamp_seconds=frame.timestamp_seconds,
                top_category="safe",
                is_nsfw=False,
                overall_severity=0,
                categories=categories(),
                reason="fixture",
                raw_response={"top_category": "safe"},
            )
            for frame in frames
        ]


class FakeDetectionService:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def finalize_classification(self, *, job, metadata, frames, result) -> None:  # type: ignore[no-untyped-def]
        self.calls.append({"job": job, "metadata": metadata, "frames": frames, "result": result})


async def enqueue(queue_repository: InMemoryVideoQueueRepository) -> VideoJob:
    result = await queue_repository.enqueue_video_job(request())
    return result.job


@pytest.mark.asyncio
async def test_processor_runs_pipeline_and_marks_classified(test_settings, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    settings = test_settings.model_copy(update={"video_temp_root": str(tmp_path), "queue_max_attempts": 2})
    queue_repository = InMemoryVideoQueueRepository()
    queue_service = QueueService(queue_repository)
    job = await enqueue(queue_repository)
    state = FakeJobStateRepository()
    detection = FakeDetectionService()

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"video")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        processor = VideoJobProcessor(
            settings=settings,
            queue_service=queue_service,
            job_state_repository=state,
            frame_extraction_service=FakeFrameExtractionService(tmp_path),
            gpu_service=FakeGpuService(),
            aggregation_service=AggregationService(settings),
            detection_service=detection,
            http_client=client,
        )

        await processor.process(job)

    updated = await queue_service.get_status_by_job_id("job")
    assert updated is not None
    assert updated.status == VideoJobStatus.CLASSIFIED
    assert updated.attempts == 1
    assert state.processing == ["job"]
    assert len(detection.calls) == 1
    assert detection.calls[0]["metadata"].frames_extracted == 1
    assert not job_temp_dir("job", settings).exists()


@pytest.mark.asyncio
async def test_processor_marks_terminal_for_bad_video_input(test_settings, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    settings = test_settings.model_copy(update={"video_temp_root": str(tmp_path), "video_max_bytes": 1})
    queue_repository = InMemoryVideoQueueRepository()
    queue_service = QueueService(queue_repository)
    job = await enqueue(queue_repository)
    state = FakeJobStateRepository()

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"too-large")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        processor = VideoJobProcessor(
            settings=settings,
            queue_service=queue_service,
            job_state_repository=state,
            frame_extraction_service=FakeFrameExtractionService(tmp_path),
            gpu_service=FakeGpuService(),
            aggregation_service=AggregationService(settings),
            detection_service=FakeDetectionService(),
            http_client=client,
        )

        with pytest.raises(VideoJobProcessingError) as exc_info:
            await processor.process(job)

    updated = await queue_service.get_status_by_job_id("job")
    assert updated is not None
    assert updated.status == VideoJobStatus.FAILED_TERMINAL
    assert updated.last_error_code == "video_too_large"
    assert exc_info.value.failure.retryable is False
    assert state.failed == [("job", VideoJobStatus.FAILED_TERMINAL, "video_too_large")]


def test_http_500_is_retryable_until_max_attempts() -> None:
    request_obj = httpx.Request("GET", "https://example.com/video.mp4")
    response = httpx.Response(503, request=request_obj)
    failure = classify_processing_error(
        httpx.HTTPStatusError("unavailable", request=request_obj, response=response),
        attempts=1,
        max_attempts=3,
    )

    assert failure.status == VideoJobStatus.FAILED_RETRYABLE
    assert failure.retryable is True


def test_http_500_becomes_terminal_at_max_attempts() -> None:
    request_obj = httpx.Request("GET", "https://example.com/video.mp4")
    response = httpx.Response(503, request=request_obj)
    failure = classify_processing_error(
        httpx.HTTPStatusError("unavailable", request=request_obj, response=response),
        attempts=3,
        max_attempts=3,
    )

    assert failure.status == VideoJobStatus.FAILED_TERMINAL
    assert failure.retryable is False
