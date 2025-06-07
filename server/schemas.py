from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


class NoteCreate(BaseModel):
    video_id: str
    video_title: Optional[str] = None
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


class NoteRead(BaseModel):
    id: int
    video_id: str
    video_title: Optional[str]
    note_timestamp: str
    note: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
