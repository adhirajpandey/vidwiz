from pydantic import Field, field_validator

from src.models import ApiModel
from src.notes.schemas import NoteRead


class TaskRetrievedResponse(ApiModel):
    task_id: int
    task_type: str
    task_details: dict | None = None
    retry_count: int
    message: str


class TaskTimeoutResponse(ApiModel):
    message: str
    timeout: bool = True


class TaskSubmitResponse(ApiModel):
    message: str
    task_id: int
    status: str


class TaskPollParams(ApiModel):
    task_type: str
    timeout: int
    poll_interval: int
    max_retries: int
    in_progress_timeout: int


class TaskResultRequest(ApiModel):
    video_id: str
    success: bool
    transcript: list[dict] | None = None
    metadata: dict | None = None
    error_message: str | None = None

    @field_validator("transcript")
    @classmethod
    def validate_transcript_format(cls, value: list[dict] | None) -> list[dict] | None:
        if value is None:
            return value
        for item in value:
            if not isinstance(item, dict):
                raise ValueError("transcript items must be dictionaries")
            if "text" not in item:
                raise ValueError("transcript items must contain 'text' field")
        return value

    @field_validator("metadata")
    @classmethod
    def validate_metadata_format(cls, value: dict | None) -> dict | None:
        if value is None:
            return value
        if not isinstance(value, dict):
            raise ValueError("metadata must be a dictionary")
        return value


class TranscriptWrite(ApiModel):
    transcript: list[dict]

    @field_validator("transcript")
    @classmethod
    def validate_transcript_format(cls, value: list[dict]) -> list[dict]:
        for item in value:
            if not isinstance(item, dict):
                raise ValueError("transcript items must be dictionaries")
            if "text" not in item:
                raise ValueError("transcript items must contain 'text' field")
        return value


class MetadataWrite(ApiModel):
    metadata: dict


class SummaryWrite(ApiModel):
    summary: str | None = Field(default=None, max_length=10000)


class VideoNotesResponse(ApiModel):
    video_id: str
    notes: list[NoteRead]
    message: str
