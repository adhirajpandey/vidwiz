from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from src.models import ApiModel


class NoteCreate(ApiModel):
    timestamp: str
    text: str | None = None
    video_title: str | None = None

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: str) -> str:
        if ":" not in value:
            raise ValueError("timestamp must contain at least one ':'")
        if sum(char.isdigit() for char in value) < 2:
            raise ValueError("timestamp must contain at least two numbers")
        return value

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed if trimmed else None


class NoteUpdate(ApiModel):
    text: str | None = None
    generated_by_ai: bool | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value


class NoteRead(ApiModel):
    id: int
    video_id: str
    timestamp: str
    text: str | None
    generated_by_ai: bool
    created_at: datetime
    updated_at: datetime
    user_id: int


class MessageResponse(ApiModel):
    message: str


class NoteIdPath(ApiModel):
    note_id: int = Field(ge=1)
