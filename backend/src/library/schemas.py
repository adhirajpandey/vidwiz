from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from src.models import ApiModel
from src.videos.models import OverviewStatus, TranscriptStatus

LibrarySort = Literal[
    "activity_desc",
    "added_desc",
    "title_asc",
    "title_desc",
    "moments_desc",
    "chats_desc",
]
LibraryView = Literal["all", "with_moments", "with_chats"]


class LibraryParams(ApiModel):
    q: str = ""
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=50)
    sort: LibrarySort = "activity_desc"
    view: LibraryView = "all"

    @field_validator("q")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        trimmed = value.strip()
        return trimmed if len(trimmed) >= 2 else ""


class LatestMoment(ApiModel):
    text: str
    kind: Literal["note", "ai", "quote"]


class LibraryCounts(ApiModel):
    all: int
    with_moments: int
    with_chats: int


class LibraryVideo(ApiModel):
    video_id: str
    title: str | None
    metadata: dict | None
    transcript_status: TranscriptStatus
    overview_status: OverviewStatus
    moment_count: int
    chat_count: int
    latest_moment: LatestMoment | None
    added_at: datetime
    last_activity_at: datetime


class LibraryResponse(ApiModel):
    videos: list[LibraryVideo]
    total: int
    counts: LibraryCounts
    page: int
    per_page: int
    total_pages: int
