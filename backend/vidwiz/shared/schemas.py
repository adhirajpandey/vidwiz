from pydantic import BaseModel, field_validator, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VideoCreate(BaseModel):
    video_id: str
    title: str
    transcript_available: Optional[bool] = False


class VideoRead(BaseModel):
    id: int
    video_id: str
    title: Optional[str]
    metadata: Optional[dict] = Field(default=None, validation_alias="video_metadata")
    transcript_available: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class VideoUpdate(BaseModel):
    title: Optional[str] = None
    transcript_available: Optional[bool] = None

    model_config = {
        "from_attributes": True,
        "extra": "forbid",
    }


class NoteCreate(BaseModel):
    video_id: str
    video_title: Optional[str] = None
    timestamp: str
    text: Optional[str] = None

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_contain_colon(cls, v):
        if ":" not in v:
            raise ValueError("timestamp must contain at least one ':'")
        if sum(c.isdigit() for c in v) < 2:
            raise ValueError("timestamp must contain at least two numbers")
        return v


class NoteRead(BaseModel):
    id: int
    video_id: str
    timestamp: str
    text: Optional[str]
    generated_by_ai: bool
    created_at: datetime
    updated_at: datetime
    video: Optional[VideoRead] = None
    user_id: int
    model_config = {"from_attributes": True}


class NoteUpdate(BaseModel):
    text: str
    generated_by_ai: Optional[bool] = None

    @field_validator("text")
    @classmethod
    def validate_string_type(cls, v):
        if v is not None and not isinstance(v, str):
            raise ValueError("Field must be a string")
        return v

    model_config = {
        "from_attributes": True,
        "extra": "forbid",
    }


class TranscriptResult(BaseModel):
    task_id: int
    video_id: str
    success: bool
    transcript: Optional[list] = None
    error_message: Optional[str] = None

    @field_validator("transcript")
    @classmethod
    def validate_transcript_format(cls, v):
        if v is not None:
            if not isinstance(v, list):
                raise ValueError("transcript must be a list")
            for item in v:
                if not isinstance(item, dict):
                    raise ValueError("transcript items must be dictionaries")
                if "text" not in item:
                    raise ValueError("transcript items must contain 'text' field")
        return v


class MetadataResult(BaseModel):
    task_id: int
    video_id: str
    success: bool
    metadata: Optional[dict] = None
    error_message: Optional[str] = None

    @field_validator("metadata")
    @classmethod
    def validate_metadata_format(cls, v):
        if v is not None:
            if not isinstance(v, dict):
                raise ValueError("metadata must be a dictionary")
        return v


class UserCreate(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        if not v or not v.strip():
            raise ValueError("Username cannot be empty")
        if len(v.strip()) < 3:
            raise ValueError("Username must be at least 3 characters long")
        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if not v:
            raise ValueError("Password cannot be empty")
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters long")
        return v

    model_config = {
        "extra": "forbid",
    }


class UserLogin(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        if not v or not v.strip():
            raise ValueError("Username cannot be empty")
        return v.strip()

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if not v:
            raise ValueError("Password cannot be empty")
        return v

    model_config = {
        "extra": "forbid",
    }


class UserProfileRead(BaseModel):
    id: int
    username: str
    name: Optional[str] = None
    profile_image_url: Optional[str] = None
    ai_notes_enabled: bool
    token_exists: bool
    long_term_token: Optional[str] = None
    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    ai_notes_enabled: bool

    model_config = {
        "from_attributes": True,
        "extra": "forbid",
    }


class TokenResponse(BaseModel):
    message: str
    token: str
    model_config = {"from_attributes": True}


class TokenRevokeResponse(BaseModel):
    message: str
    model_config = {"from_attributes": True}
