from datetime import datetime
from pydantic import Field, field_validator

from src.models import ApiModel
from src.videos.models import OverviewStatus, TranscriptStatus
from src.videos.utils import normalize_youtube_video_id


class KeyPoint(ApiModel):
    """A key idea from the overview, at the time the video explains it."""

    text: str
    start_seconds: float
    end_seconds: float


class VideoRead(ApiModel):
    id: int
    video_id: str
    title: str | None
    metadata: dict | None = Field(default=None, validation_alias="video_metadata")
    transcript_status: TranscriptStatus
    summary: str | None = None
    overview_status: OverviewStatus
    suggested_questions: list[str] | None = None
    key_points: list["KeyPoint"] | None = None
    overview_model: str | None = None
    created_at: datetime
    updated_at: datetime


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
    # Segments are present only when ready.
    status: TranscriptStatus
    segments: list[TranscriptSegment]


class AskStatus(ApiModel):
    unlocked: bool
    # Credits charged when the first conversation for the video starts.
    cost: int
