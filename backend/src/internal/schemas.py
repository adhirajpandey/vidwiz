from typing import Annotated

from pydantic import AfterValidator, Field, StringConstraints, field_validator

from src.models import ApiModel
from src.videos.utils import normalize_youtube_video_id


def _require_text(items: list[dict]) -> list[dict]:
    if any("text" not in item for item in items):
        raise ValueError("transcript items must contain 'text' field")
    return items


Transcript = Annotated[list[dict], AfterValidator(_require_text)]


class TaskRetrievedResponse(ApiModel):
    task_id: int
    task_type: str
    task_details: dict | None = None
    retry_count: int
    message: str


class TaskSubmitResponse(ApiModel):
    message: str
    task_id: int
    status: str


class TaskPollParams(ApiModel):
    task_type: str
    timeout: int


class ResolvedVideo(ApiModel):
    video_id: str
    title: str | None = None

    @field_validator("video_id")
    @classmethod
    def validate_video_id(cls, value: str) -> str:
        return normalize_youtube_video_id(value)


class CandidateVideo(ApiModel):
    video_id: str
    title: str | None = None
    channel: str | None = None


class TaskResultRequest(ApiModel):
    # Video tasks send video_id. Title tasks send resolved when one video was
    # chosen confidently, or candidates when the user has to pick.
    video_id: str | None = None
    resolved: ResolvedVideo | None = None
    candidates: list[CandidateVideo] | None = Field(default=None, max_length=10)
    success: bool
    transcript: Transcript | None = None
    metadata: dict | None = None
    error_message: str | None = None


class TranscriptWrite(ApiModel):
    transcript: Transcript


class MetadataWrite(ApiModel):
    metadata: dict


QuestionText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
]


class MiscellaneousDataWrite(ApiModel):
    suggested_questions: list[QuestionText] = Field(min_length=3, max_length=3)

    @field_validator("suggested_questions")
    @classmethod
    def validate_unique_questions(cls, value: list[str]) -> list[str]:
        if len({question.casefold() for question in value}) != len(value):
            raise ValueError("suggested questions must be unique")
        return value


class SummaryWrite(ApiModel):
    summary: str | None = Field(default=None, max_length=10000)
    miscellaneous_data: MiscellaneousDataWrite | None = None


class PendingMoment(ApiModel):
    id: int
    video_id: str
    at_seconds: int
    user_id: int


class PendingMomentsResponse(ApiModel):
    video_id: str
    moments: list[PendingMoment]


class MomentAiWrite(ApiModel):
    """Worker result. Null marks the generation as failed."""

    ai_text: str | None = Field(default=None, max_length=1000)
