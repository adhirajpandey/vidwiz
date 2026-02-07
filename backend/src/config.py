from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = Field(default="local", alias="ENVIRONMENT")
    db_url: str = Field(default="sqlite:///./vidwiz.db", alias="DB_URL")
    secret_key: str | None = Field(default=None, alias="SECRET_KEY")
    admin_token: str | None = Field(default=None, alias="ADMIN_TOKEN")
    jwt_expiry_hours: int = Field(default=24, alias="JWT_EXPIRY_HOURS")
    google_client_id: str | None = Field(default=None, alias="GOOGLE_CLIENT_ID")
    sqs_ai_note_queue_url: str | None = Field(
        default=None, alias="SQS_AI_NOTE_QUEUE_URL"
    )
    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(
        default=None, alias="AWS_SECRET_ACCESS_KEY"
    )
    aws_region: str = Field(default="ap-south-1", alias="AWS_REGION")
    rate_limit_enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    rate_limit_default: str = Field(default="60/minute", alias="RATE_LIMIT_DEFAULT")
    rate_limit_auth: str = Field(default="10/minute", alias="RATE_LIMIT_AUTH")
    rate_limit_conversations: str = Field(
        default="20/minute", alias="RATE_LIMIT_CONVERSATIONS"
    )
    rate_limit_videos: str = Field(default="30/minute", alias="RATE_LIMIT_VIDEOS")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
