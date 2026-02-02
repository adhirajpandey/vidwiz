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
    created_at: datetime
    updated_at: datetime


class VideoSearchItem(ApiModel):
    video_id: str
    title: str | None = None
    metadata: dict | None = None


class VideoListResponse(ApiModel):
    videos: list[VideoSearchItem]
    total: int
    page: int
    per_page: int
    total_pages: int




class VideoStreamPayload(ApiModel):
    event: Literal["snapshot", "update", "done"]
    video: VideoRead


class VideoListParams(ApiModel):
    q: str = ""
    page: int = 1
    per_page: int = 10
    sort: str = "created_at_desc"

    @field_validator("q")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        if not value:
            return ""
        trimmed = value.strip()
        if len(trimmed) < 2:
            return ""
        return trimmed

    @field_validator("page")
    @classmethod
    def validate_page(cls, value: int) -> int:
        return max(1, value)

    @field_validator("per_page")
    @classmethod
    def validate_per_page(cls, value: int) -> int:
        if value < 1:
            return 10
        return min(50, value)


class VideoIdPath(ApiModel):
    video_id: str

    @field_validator("video_id")
    @classmethod
    def validate_video_id(cls, value: str) -> str:
        return normalize_youtube_video_id(value)
