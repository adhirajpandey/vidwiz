from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from src.models import ApiModel
from src.videos.utils import normalize_youtube_video_id


class VideoRead(ApiModel):
    id: int
    video_id: str
    title: str | None
    metadata: dict | None = Field(default=None, validation_alias="video_metadata")
    transcript_available: bool
    summary: str | None = None
    suggested_questions: list[str] | None = None
    created_at: datetime
    updated_at: datetime


class VideoStreamPayload(ApiModel):
    event: Literal["snapshot", "update", "done"]
    video: VideoRead


class VideoIdPath(ApiModel):
    video_id: str

    @field_validator("video_id")
    @classmethod
    def validate_video_id(cls, value: str) -> str:
        return normalize_youtube_video_id(value)


class TranscriptSegment(ApiModel):
    start_seconds: float
    end_seconds: float
    text: str


class TranscriptRead(ApiModel):
    video_id: str
    # ready: segments present; processing: still being fetched;
    # unavailable: fetching failed for good, so there is no transcript.
    status: Literal["ready", "processing", "unavailable"]
    segments: list[TranscriptSegment]
