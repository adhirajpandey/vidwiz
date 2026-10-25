import json
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]


class Settings(BaseSettings):
    environment: NonEmptyStr = Field(alias="ENVIRONMENT")
    # PostgreSQL only: migrations and search use PostgreSQL features.
    db_url: NonEmptyStr = Field(alias="DB_URL")
    secret_key: NonEmptyStr = Field(alias="SECRET_KEY")
    internal_api_admin_token: NonEmptyStr = Field(
        alias="VIDWIZ_INTERNAL_API_ADMIN_TOKEN"
    )
    jwt_expiry_hours: int = Field(default=168, alias="JWT_EXPIRY_HOURS")
    google_client_id: NonEmptyStr = Field(alias="GOOGLE_CLIENT_ID")
    sqs_ai_note_queue_url: str = Field(alias="SQS_AI_NOTE_QUEUE_URL")
    sqs_ai_summary_queue_url: str = Field(alias="SQS_AI_SUMMARY_QUEUE_URL")
    aws_access_key_id: str = Field(alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="ap-south-1", alias="AWS_REGION")
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_default: str = Field(default="60/minute", alias="RATE_LIMIT_DEFAULT")
    rate_limit_auth: str = Field(default="10/minute", alias="RATE_LIMIT_AUTH")
    rate_limit_conversations: str = Field(
        default="20/minute", alias="RATE_LIMIT_CONVERSATIONS"
    )
    rate_limit_videos: str = Field(default="30/minute", alias="RATE_LIMIT_VIDEOS")
    dodo_payments_api_key: str = Field(alias="DODO_PAYMENTS_API_KEY")
    dodo_payments_webhook_key: str = Field(alias="DODO_PAYMENTS_WEBHOOK_KEY")
    dodo_payments_environment: NonEmptyStr = Field(alias="DODO_PAYMENTS_ENVIRONMENT")
    dodo_payments_return_url: str = Field(alias="DODO_PAYMENTS_RETURN_URL")
    dodo_credit_products: list["CreditProductConfig"] = Field(
        alias="DODO_CREDIT_PRODUCTS"
    )
    signup_grant_amount: int = Field(default=100, alias="SIGNUP_GRANT_AMOUNT")
    wiz_chat_cost: int = Field(default=5, alias="WIZ_CHAT_COST")
    ai_moment_cost: int = Field(default=1, alias="AI_MOMENT_COST")
    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL"
    )
    wiz_model: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1)
    ] = Field(default="minimax/minimax-m2.5", alias="WIZ_MODEL")
    wiz_user_daily_quota: int = Field(default=20, alias="WIZ_USER_DAILY_QUOTA")
    wiz_guest_daily_quota: int = Field(default=5, alias="WIZ_GUEST_DAILY_QUOTA")
    wiz_max_tokens: int = Field(default=8192, alias="WIZ_MAX_TOKENS")
    # Library Ask: a small model turns the question into search terms, full-text
    # search gathers candidates, and Jev scores each candidate's relevance.
    ask_query_model: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1)
    ] = Field(default="z-ai/glm-5.3-flash", alias="ASK_QUERY_MODEL")
    ask_candidates: int = Field(default=48, ge=1, le=200, alias="ASK_CANDIDATES")
    ask_max_sources: int = Field(default=8, ge=1, le=30, alias="ASK_MAX_SOURCES")
    # A question only about a period ("this week") reads its newest moments.
    ask_time_range_max_sources: int = Field(
        default=25, ge=1, le=50, alias="ASK_TIME_RANGE_MAX_SOURCES"
    )
    jev_enabled: bool = Field(default=True, alias="JEV_ENABLED")
    jev_model: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1)
    ] = Field(default="typesafe/jev-1.14-20261014", alias="JEV_MODEL")
    jev_decisions_url: str = Field(
        default="https://openrouter.ai/api/alpha/decisions", alias="JEV_DECISIONS_URL"
    )
    jev_relevance_threshold: float = Field(
        default=0.5, ge=0, le=1, alias="JEV_RELEVANCE_THRESHOLD"
    )
    s3_transcript_bucket_name: str | None = Field(
        default=None, alias="S3_TRANSCRIPT_BUCKET_NAME"
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_service_name: str = Field(default="vidwiz-api", alias="LOG_SERVICE_NAME")
    loki_url: str | None = Field(default=None, alias="LOKI_URL")
    loki_username: str | None = Field(default=None, alias="LOKI_USERNAME")
    loki_password: str | None = Field(default=None, alias="LOKI_PASSWORD")

    @field_validator("dodo_credit_products", mode="before")
    @classmethod
    def parse_dodo_credit_products(cls, value):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError("DODO_CREDIT_PRODUCTS must be valid JSON") from exc
        if not isinstance(value, list):
            raise ValueError("DODO_CREDIT_PRODUCTS must be a JSON list")
        return value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


class CreditProductConfig(BaseModel):
    product_id: str
    credits: int
    price_inr: int
    name: str | None = None

    @field_validator("credits", "price_inr")
    @classmethod
    def ensure_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be greater than 0")
        return value


settings = Settings()
