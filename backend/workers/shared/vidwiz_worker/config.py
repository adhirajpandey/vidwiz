from dataclasses import dataclass
import os


def _required(name: str) -> str:
    value = os.getenv(name)
    assert value, f"{name} is not set"
    return value


@dataclass(frozen=True)
class WorkerSettings:
    transcript_bucket_name: str
    internal_api_base_url: str
    internal_api_admin_token: str
    openrouter_api_key: str
    openrouter_base_url: str
    openrouter_model: str
    transcript_buffer_seconds: int
    context_segments: int
    max_note_length: int
    min_note_length: int
    max_summary_length: int
    min_summary_length: int
    max_question_length: int
    min_question_length: int
    max_retries: int
    request_timeout: int
    transcript_fetch_max_retries: int
    transcript_fetch_retry_delay: int

    @property
    def openrouter_endpoint(self) -> str:
        return f"{self.openrouter_base_url.rstrip('/')}/chat/completions"

    @classmethod
    def from_env(cls) -> "WorkerSettings":
        min_question_length = int(os.getenv("MIN_QUESTION_LENGTH", "20"))
        max_question_length = int(os.getenv("MAX_QUESTION_LENGTH", "120"))
        if not 1 <= min_question_length <= max_question_length <= 500:
            raise ValueError(
                "question length settings must satisfy "
                "1 <= MIN_QUESTION_LENGTH <= MAX_QUESTION_LENGTH <= 500"
            )
        return cls(
            transcript_bucket_name=_required("S3_TRANSCRIPT_BUCKET_NAME"),
            internal_api_base_url=_required("VIDWIZ_INTERNAL_API_BASE_URL"),
            internal_api_admin_token=_required("VIDWIZ_INTERNAL_API_ADMIN_TOKEN"),
            openrouter_api_key=_required("OPENROUTER_API_KEY"),
            openrouter_base_url=os.getenv(
                "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
            ),
            openrouter_model=os.getenv(
                "OPENROUTER_MODEL", "google/gemini-3-flash-preview"
            ),
            transcript_buffer_seconds=int(os.getenv("TRANSCRIPT_BUFFER_SECONDS", "15")),
            context_segments=int(os.getenv("CONTEXT_SEGMENTS", "15")),
            max_note_length=int(os.getenv("MAX_NOTE_LENGTH", "120")),
            min_note_length=int(os.getenv("MIN_NOTE_LENGTH", "40")),
            max_summary_length=int(os.getenv("MAX_SUMMARY_LENGTH", "800")),
            min_summary_length=int(os.getenv("MIN_SUMMARY_LENGTH", "200")),
            max_question_length=max_question_length,
            min_question_length=min_question_length,
            max_retries=int(os.getenv("MAX_RETRIES", "3")),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "30")),
            transcript_fetch_max_retries=int(
                os.getenv("TRANSCRIPT_FETCH_MAX_RETRIES", "5")
            ),
            transcript_fetch_retry_delay=int(
                os.getenv("TRANSCRIPT_FETCH_RETRY_DELAY", "2")
            ),
        )
