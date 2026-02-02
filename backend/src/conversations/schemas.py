from datetime import datetime

from pydantic import ConfigDict, Field, field_validator

from src.models import ApiModel
from src.videos.utils import normalize_youtube_video_id


class ConversationCreate(ApiModel):
    video_id: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("video_id")
    @classmethod
    def validate_video_id(cls, value: str) -> str:
        return normalize_youtube_video_id(value)


class ConversationRead(ApiModel):
    id: int
    video_id: str
    created_at: datetime
    updated_at: datetime


class ConversationIdPath(ApiModel):
    conversation_id: int = Field(ge=1)


class MessageCreate(ApiModel):
    message: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("message cannot be empty")
        return trimmed


class MessageRead(ApiModel):
    id: int
    conversation_id: int
    role: str
    content: str
    metadata: dict | None = Field(default=None, validation_alias="metadata_")
    created_at: datetime


class ChatProcessingResponse(ApiModel):
    status: str
    message: str
