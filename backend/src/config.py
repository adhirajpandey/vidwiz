from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = Field(default="local", alias="ENVIRONMENT")
    db_url: str = Field(default="sqlite:///./vidwiz.db", alias="DB_URL")
    secret_key: str | None = Field(default=None, alias="SECRET_KEY")
    admin_token: str | None = Field(default=None, alias="ADMIN_TOKEN")
    jwt_expiry_hours: int = Field(default=24, alias="JWT_EXPIRY_HOURS")
    google_client_id: str | None = Field(default=None, alias="GOOGLE_CLIENT_ID")
    sqs_ai_note_queue_url: str | None = Field(default=None, alias="SQS_AI_NOTE_QUEUE_URL")
    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="ap-south-1", alias="AWS_REGION")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
