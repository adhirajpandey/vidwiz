from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConversationsSettings(BaseSettings):
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    gemini_model_name: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL_NAME")
    wiz_user_daily_quota: int = Field(default=20, alias="WIZ_USER_DAILY_QUOTA")
    wiz_guest_daily_quota: int = Field(default=5, alias="WIZ_GUEST_DAILY_QUOTA")
    s3_bucket_name: str | None = Field(default=None, alias="S3_BUCKET_NAME")
    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str | None = Field(default=None, alias="AWS_REGION")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


conversations_settings = ConversationsSettings()
