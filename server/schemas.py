from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class NoteCreate(BaseModel):
    video_id: str
    video_title: str
    note_timestamp: str
    note: Optional[str] = None

    @field_validator("note_timestamp")
    @classmethod
    def timestamp_must_contain_colon(cls, v):
        if ":" not in v:
            raise ValueError("note_timestamp must contain at least one ':'")
        if sum(c.isdigit() for c in v) < 2:
            raise ValueError("note_timestamp must contain at least two numbers")
        return v

    @field_validator("video_title")
    @classmethod
    def video_title_cannot_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("video_title cannot be empty")
        return v.strip()


class NoteRead(BaseModel):
    id: int
    video_id: str
    video_title: str
    note_timestamp: str
    note: Optional[str]
    ai_note: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NoteUpdate(BaseModel):
    note: Optional[str] = None
    ai_note: Optional[str] = None

    @field_validator("*")
    @classmethod
    def validate_at_least_one_field(cls, v, info):
        if info.field_name == "note" and v is None and info.data.get("ai_note") is None:
            raise ValueError("At least one of 'note' or 'ai_note' must be provided")
        return v

    @field_validator("note", "ai_note")
    @classmethod
    def validate_string_type(cls, v):
        if v is not None and not isinstance(v, str):
            raise ValueError("Field must be a string")
        return v

    model_config = {
        "from_attributes": True,
        "extra": "forbid"  # Reject any fields not defined in the model
    }
