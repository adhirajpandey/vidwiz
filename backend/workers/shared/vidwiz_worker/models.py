from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class Moment(BaseModel):
    """An AI moment job, as queued by the API and the dispatcher."""

    id: int
    video_id: str
    at_seconds: int = Field(ge=0)
    user_id: int


class SummaryRequest(BaseModel):
    video_id: str


class SummaryArtifacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: str
    suggested_questions: list[str] = Field(min_length=3, max_length=3)

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("summary must not be blank")
        return normalized

    @field_validator("suggested_questions")
    @classmethod
    def normalize_questions(cls, value: list[str]) -> list[str]:
        normalized = [" ".join(question.split()) for question in value]
        if any(not question for question in normalized):
            raise ValueError("suggested questions must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_unique_questions(self) -> "SummaryArtifacts":
        if len({question.casefold() for question in self.suggested_questions}) != 3:
            raise ValueError("suggested questions must be unique")
        return self


class TranscriptSegment(BaseModel):
    offset: float
    text: str


class RelevantTranscriptContext(BaseModel):
    timestamp: float
    text: str
    before: list[TranscriptSegment]
    after: list[TranscriptSegment]
