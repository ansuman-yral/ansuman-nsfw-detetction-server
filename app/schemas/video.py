from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.constants import VideoJobStatus


class VideoDetectRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "job_id": "nsfw:video-id:nsfw_policy_v1:",
                    "video_id": "video-id",
                    "publisher_user_id": "principal-or-user-id",
                    "source_video_uri": "https://link.storjshare.io/raw/bucket/path/video.mp4",
                    "post_id": "post-id-or-null",
                    "canister_id": "canister-id-or-null",
                    "source_object_version": "",
                    "upload_event_id": "event-id-or-null",
                    "upload_created_at": "2026-06-05T00:00:00Z",
                    "policy_version": "nsfw_policy_v1",
                    "trace_id": "trace-id",
                }
            ]
        }
    )

    job_id: str = Field(min_length=1)
    video_id: str = Field(min_length=1)
    publisher_user_id: str = Field(min_length=1)
    source_video_uri: str = Field(min_length=1)
    post_id: str | None = None
    canister_id: str | None = None
    source_object_version: str = ""
    upload_event_id: str | None = None
    upload_created_at: datetime | None = None
    policy_version: str = Field(default="nsfw_policy_v1", min_length=1)
    trace_id: str | None = None


class VideoDetectResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "job_id": "nsfw:video-id:nsfw_policy_v1:",
                    "video_id": "video-id",
                    "status": "queued",
                    "trace_id": "trace-id",
                }
            ]
        }
    )

    job_id: str
    video_id: str
    status: VideoJobStatus
    trace_id: str | None = None


class VideoStatusResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "job_id": "nsfw:video-id:nsfw_policy_v1:",
                    "video_id": "video-id",
                    "status": "classified",
                    "trace_id": "trace-id",
                    "attempts": 1,
                    "last_error_code": None,
                    "last_error_message": None,
                    "final_result": {"final_is_nsfw": False, "final_score": 0.0},
                }
            ]
        }
    )

    job_id: str
    video_id: str
    status: VideoJobStatus
    trace_id: str | None = None
    attempts: int = 0
    last_error_code: str | None = None
    last_error_message: str | None = None
    final_result: dict[str, object] | None = None
