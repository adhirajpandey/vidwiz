from pydantic import Field

from src.models import ApiModel


class CheckoutSessionRequest(ApiModel):
    product_id: str = Field(min_length=1)
    quantity: int = Field(default=1, ge=1, le=100)


class CheckoutSessionResponse(ApiModel):
    checkout_url: str
    session_id: str


class WebhookResponse(ApiModel):
    status: str
