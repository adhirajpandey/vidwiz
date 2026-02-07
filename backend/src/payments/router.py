import json

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user_id
from src.database import get_db
from src.exceptions import BadRequestError
from src.payments import service as payments_service
from src.payments.schemas import (
    CheckoutSessionRequest,
    CheckoutSessionResponse,
    WebhookResponse,
)


router = APIRouter(prefix="/v2/payments", tags=["Payments"])


@router.post(
    "/checkout",
    response_model=CheckoutSessionResponse,
    status_code=status.HTTP_201_CREATED,
    description="Create a Dodo Payments checkout session for credits.",
)
async def create_checkout(
    request: Request,
    response: Response,
    payload: CheckoutSessionRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> CheckoutSessionResponse:
    result = await payments_service.create_checkout_session(
        db, user_id, payload.product_id, payload.quantity
    )
    return CheckoutSessionResponse(**result)


@router.post(
    "/webhooks/dodo",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    description="Handle Dodo Payments webhooks.",
)
async def dodo_webhook(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    signature: str | None = Header(default=None, alias="webhook-signature"),
    webhook_id: str | None = Header(default=None, alias="webhook-id"),
    timestamp: str | None = Header(default=None, alias="webhook-timestamp"),
) -> WebhookResponse:
    payload_bytes = await request.body()
    headers = {
        "webhook-id": webhook_id or "",
        "webhook-timestamp": timestamp or "",
        "webhook-signature": signature or "",
    }
    payments_service.verify_webhook_signature(payload_bytes, headers)

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except json.JSONDecodeError:
        raise BadRequestError("Invalid webhook payload")

    payments_service.handle_webhook_event(db, payload)
    return WebhookResponse(status="ok")
