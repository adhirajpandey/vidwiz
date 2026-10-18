from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from src.conversations.models import ConversationScope
from src.conversations.parts import MessagePart, stored_parts
from src.models import ApiModel
from src.videos.utils import normalize_youtube_video_id


class ConversationCreate(ApiModel):
    """A video conversation needs video_id; a library conversation must omit it."""

    scope: ConversationScope = ConversationScope.VIDEO
    video_id: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("video_id")
    @classmethod
    def validate_video_id(cls, value: str | None) -> str | None:
        return normalize_youtube_video_id(value) if value is not None else None

    @model_validator(mode="after")
    def match_scope(self) -> "ConversationCreate":
        if self.scope == ConversationScope.VIDEO and self.video_id is None:
            raise ValueError("video_id is required for a video conversation")
        if self.scope == ConversationScope.LIBRARY and self.video_id is not None:
            raise ValueError("A library conversation has no video_id")
        return self


class ConversationRead(ApiModel):
    id: int
    scope: ConversationScope
    video_id: str | None
    created_at: datetime
    updated_at: datetime


class ConversationSummary(ApiModel):
    id: int
    scope: ConversationScope
    video_id: str | None
    video_title: str | None
    # The first question, trimmed, so a list of chats is readable.
    title: str
    message_count: int
    last_message_at: datetime


class ConversationList(ApiModel):
    conversations: list[ConversationSummary]
    page: int
    per_page: int
    has_more: bool


class ConversationIdPath(ApiModel):
    conversation_id: int = Field(ge=1)


class MessageCreate(ApiModel):
    message: str
    # Only block responses are generated; the field stays for existing clients.
    parts_version: Literal[2] = 2

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
    parts: list[MessagePart] = Field(default_factory=list)

    @model_validator(mode="after")
    def resolve_parts(self):
        self.parts = stored_parts(self.content, self.metadata)
        return self


class ChatProcessingResponse(ApiModel):
    status: str
    message: str
