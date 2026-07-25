from typing import Any

from pydantic import BaseModel


class Video(BaseModel):
    created_at: str
    id: int
    title: str | None = None
    transcript_available: bool
    updated_at: str
    video_id: str


class Note(BaseModel):
    created_at: str | None = None
    generated_by_ai: bool | None = None
    id: int
    text: Any = None
    timestamp: str
    updated_at: str | None = None
    user_id: int
    video: Video | None = None
    video_id: str


class SummaryRequest(BaseModel):
    video_id: str


class TranscriptSegment(BaseModel):
    offset: float
    text: str


class RelevantTranscriptContext(BaseModel):
    timestamp: float
    text: str
    before: list[TranscriptSegment]
    after: list[TranscriptSegment]
