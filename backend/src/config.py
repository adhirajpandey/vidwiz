import logging
from pydantic import BaseModel, Field, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = Field(alias="ENVIRONMENT")
    db_url: str = Field(default="sqlite:///./vidwiz.db", alias="DB_URL")
    secret_key: str = Field(alias="SECRET_KEY")
    admin_token: str = Field(alias="ADMIN_TOKEN")
    jwt_expiry_hours: int = Field(default=24, alias="JWT_EXPIRY_HOURS")
    google_client_id: str = Field(alias="GOOGLE_CLIENT_ID")
    sqs_ai_note_queue_url: str = Field(alias="SQS_AI_NOTE_QUEUE_URL")
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
    dodo_payments_environment: str = Field(alias="DODO_PAYMENTS_ENVIRONMENT")
    dodo_payments_return_url: str = Field(alias="DODO_PAYMENTS_RETURN_URL")
    dodo_credit_products: list["CreditProductConfig"] = Field(
        alias="DODO_CREDIT_PRODUCTS"
    )
    signup_grant_amount: int = Field(default=100, alias="SIGNUP_GRANT_AMOUNT")
    wiz_chat_cost: int = Field(default=5, alias="WIZ_CHAT_COST")
    ai_note_cost: int = Field(default=1, alias="AI_NOTE_COST")

    @field_validator("dodo_credit_products", mode="before")
    @classmethod
    def parse_dodo_credit_products(cls, value):
        if isinstance(value, str):
            try:
                import json

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


logger = logging.getLogger(__name__)

try:
    settings = Settings()
except ValidationError as exc:
    field_aliases = {
        name: (field.alias or name) for name, field in Settings.model_fields.items()
    }
    missing = [
        field_aliases.get(err.get("loc", [None])[-1], err.get("loc", [None])[-1])
        for err in exc.errors()
        if err.get("type") == "missing"
    ]
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
    else:
        logger.error("Invalid environment configuration: %s", exc)
    raise
