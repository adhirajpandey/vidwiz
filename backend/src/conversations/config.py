from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.conversations.prompts import WIZ_SYSTEM_PROMPT_TEMPLATE


class ConversationsSettings(BaseSettings):
    openrouter_api_key: str | None = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_model_name: str = Field(default="google/gemini-3-flash-preview", alias="OPENROUTER_MODEL")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL",
    )
    wiz_system_prompt_template: str = Field(default=WIZ_SYSTEM_PROMPT_TEMPLATE)
    wiz_user_daily_quota: int = Field(default=20, alias="WIZ_USER_DAILY_QUOTA")
    wiz_guest_daily_quota: int = Field(default=5, alias="WIZ_GUEST_DAILY_QUOTA")
    s3_bucket_name: str | None = Field(default=None, alias="S3_BUCKET_NAME")
    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="ap-south-1", alias="AWS_REGION")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


conversations_settings = ConversationsSettings()
