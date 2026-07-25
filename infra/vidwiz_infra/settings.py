from pathlib import Path
from typing import Annotated, Literal, Self
from urllib.parse import urlparse

from pydantic import (
    Field,
    SecretStr,
    StringConstraints,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

AwsAccountId = Annotated[str, StringConstraints(pattern=r"^\d{12}$")]
LambdaMemory = Annotated[int, Field(ge=128, le=10_240)]
LambdaTimeout = Annotated[int, Field(ge=1, le=900)]
PositiveInt = Annotated[int, Field(ge=1)]


class ProductionSettings(BaseSettings):
    """Validated production inputs, loaded only by the CDK entrypoint."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file_encoding="utf-8",
        extra="forbid",
        hide_input_in_errors=True,
    )

    aws_account_id: AwsAccountId
    aws_region: Literal["ap-south-1"]

    dispatcher_memory_mb: LambdaMemory
    dispatcher_timeout_seconds: LambdaTimeout
    ai_note_memory_mb: LambdaMemory
    ai_note_timeout_seconds: LambdaTimeout
    ai_summary_memory_mb: LambdaMemory
    ai_summary_timeout_seconds: LambdaTimeout

    vidwiz_internal_api_base_url: str = Field(alias="VIDWIZ_INTERNAL_API_BASE_URL")
    vidwiz_internal_api_admin_token: SecretStr = Field(
        alias="VIDWIZ_INTERNAL_API_ADMIN_TOKEN"
    )
    openrouter_api_key: SecretStr
    openrouter_base_url: str
    openrouter_model: Annotated[str, StringConstraints(min_length=1)]

    transcript_buffer_seconds: PositiveInt
    context_segments: PositiveInt
    min_note_length: PositiveInt
    max_note_length: PositiveInt
    min_summary_length: PositiveInt
    max_summary_length: PositiveInt
    max_retries: PositiveInt
    request_timeout: PositiveInt
    transcript_fetch_max_retries: PositiveInt
    transcript_fetch_retry_delay: PositiveInt

    @field_validator("vidwiz_internal_api_base_url", "openrouter_base_url")
    @classmethod
    def validate_http_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("must be an absolute HTTP(S) URL")
        return value

    @field_validator("vidwiz_internal_api_admin_token", "openrouter_api_key")
    @classmethod
    def validate_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if not secret or "\n" in secret or "\r" in secret:
            raise ValueError("must be a non-empty single-line secret")
        return value

    @model_validator(mode="after")
    def validate_length_ranges(self) -> Self:
        if self.min_note_length > self.max_note_length:
            raise ValueError("MIN_NOTE_LENGTH must not exceed MAX_NOTE_LENGTH")
        if self.min_summary_length > self.max_summary_length:
            raise ValueError("MIN_SUMMARY_LENGTH must not exceed MAX_SUMMARY_LENGTH")
        return self

    @classmethod
    def from_env_file(cls, path: Path) -> Self:
        if not path.is_file():
            raise ValueError(f"Configuration file does not exist: {path}")
        return cls(_env_file=path)
