import re
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from src.models import ApiModel
from src.moments.models import AiStatus, CaptureSource, ResolveStatus
from src.videos.utils import normalize_youtube_video_id

_CLOCK = re.compile(r"^\d+(:[0-5]?\d){1,2}$")


def parse_seconds(value: int | str) -> int:
    """Accept seconds, "m:ss", or "h:mm:ss"."""
    if isinstance(value, int):
        seconds = value
    else:
        text = value.strip()
        if text.isdigit():
            seconds = int(text)
        elif _CLOCK.match(text):
            seconds = 0
            for part in text.split(":"):
                seconds = seconds * 60 + int(part)
        else:
            raise ValueError("at must be seconds, m:ss, or h:mm:ss")
    if seconds < 0:
        raise ValueError("at must not be negative")
    return seconds


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


class CaptureCreate(ApiModel):
    """One capture: a video (or its title), a time, and what to keep."""

    video: str | None = Field(default=None, description="YouTube URL or video ID")
    title: str | None = Field(
        default=None,
        max_length=500,
        description="Video title, used when the client cannot see the video ID",
    )
    channel: str | None = Field(default=None, max_length=200)
    at: int | str = Field(description="Seconds, m:ss, or h:mm:ss")
    note: str | None = Field(default=None, max_length=5000)
    ai: bool | None = Field(
        default=None, description="Request an AI line. Defaults to the user setting."
    )
    source: CaptureSource = CaptureSource.API

    model_config = ConfigDict(extra="forbid")

    @field_validator("video")
    @classmethod
    def normalize_video(cls, value: str | None) -> str | None:
        value = _clean_text(value)
        return normalize_youtube_video_id(value) if value else None

    @field_validator("title", "channel", "note")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @field_validator("at")
    @classmethod
    def validate_at(cls, value: int | str) -> int:
        return parse_seconds(value)

    @field_validator("source")
    @classmethod
    def reject_legacy(cls, value: CaptureSource) -> CaptureSource:
        if value == CaptureSource.LEGACY:
            raise ValueError("legacy is not a capture source")
        return value

    @model_validator(mode="after")
    def require_video_or_title(self) -> "CaptureCreate":
        if not self.video and not self.title:
            raise ValueError("Provide video or title")
        return self


class PassageSave(ApiModel):
    """A cited passage to keep as a moment. No AI line and no credits."""

    video_id: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)
    note: str | None = Field(default=None, max_length=5000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("video_id")
    @classmethod
    def normalize_video(cls, value: str) -> str:
        return normalize_youtube_video_id(value)

    @field_validator("note")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return _clean_text(value)

    @model_validator(mode="after")
    def ordered(self) -> "PassageSave":
        if self.end_seconds < self.start_seconds:
            raise ValueError("end_seconds must not be before start_seconds")
        return self


class ResolveCandidate(ApiModel):
    video_id: str
    title: str | None = None
    channel: str | None = None


class ResolveChoice(ApiModel):
    video_id: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("video_id")
    @classmethod
    def normalize_video(cls, value: str) -> str:
        return normalize_youtube_video_id(value)


class MomentRead(ApiModel):
    id: int
    video_id: str | None
    at_seconds: int
    quote: str | None
    quote_start_seconds: int | None
    ai_text: str | None
    ai_model: str | None = None
    note: str | None
    ai_status: AiStatus
    resolve_status: ResolveStatus
    source: CaptureSource
    pending_title: str | None
    resolve_candidates: list[ResolveCandidate] | None = None
    created_at: datetime
    updated_at: datetime


class CaptureResponse(ApiModel):
    moment: MomentRead
    merged: bool = Field(
        description="True when the capture joined an existing nearby moment"
    )


class MomentUpdate(ApiModel):
    """Fields present in the request are set; null clears them."""

    note: str | None = Field(default=None, max_length=5000)
    ai_text: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("note", "ai_text")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return _clean_text(value)


class MomentIdPath(ApiModel):
    moment_id: int = Field(ge=1)


class FeedMoment(MomentRead):
    video_title: str | None
    video_metadata: dict | None


class ResurfaceFound(ApiModel):
    state: Literal["found"] = "found"
    moment: FeedMoment


class ResurfaceNone(ApiModel):
    state: Literal["none"] = "none"


ResurfaceResponse = ResurfaceFound | ResurfaceNone


class MomentFeed(ApiModel):
    moments: list[FeedMoment]
    page: int
    per_page: int
    has_more: bool


class LegacyNoteCreate(ApiModel):
    """Body sent by the published 2.x extension to the old notes route."""

    timestamp: str
    text: str | None = None
    video_title: str | None = None

    @field_validator("text", "video_title")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        return _clean_text(value)
