from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class VideoCreate(BaseModel):
    video_id: str
    title: Optional[str] = None
    transcript_available: Optional[bool] = False


class VideoRead(BaseModel):
    id: int
    video_id: str
    title: Optional[str]
    transcript_available: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


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
