import logging
from typing import Any

from sqlalchemy.orm import Session
from standardwebhooks import Webhook, WebhookVerificationError

from src.auth.models import User
from src.config import settings
from src.credits import service as credits_service
from src.exceptions import BadRequestError, InternalServerError, NotFoundError, UnauthorizedError
from src.payments.models import (
    CreditPurchase,
    PURCHASE_STATUS_CANCELLED,
    PURCHASE_STATUS_COMPLETED,
    PURCHASE_STATUS_FAILED,
    PURCHASE_STATUS_PENDING,
    PROVIDER_DODO,
)
from src.payments.products import get_credit_product
from src.payments.schemas import CreditProductRead


logger = logging.getLogger(__name__)

EVENT_PAYMENT_SUCCEEDED = "payment.succeeded"
EVENT_PAYMENT_FAILED = "payment.failed"
EVENT_PAYMENT_CANCELLED = "payment.cancelled"
PROVIDER_SESSION_PENDING = "pending"


def verify_webhook_signature(payload: bytes, headers: dict[str, str]) -> None:
    secret = settings.dodo_payments_webhook_key
    hook = Webhook(secret)
    try:
        hook.verify(payload.decode("utf-8"), headers)
    except WebhookVerificationError as exc:
        raise UnauthorizedError("Invalid webhook signature") from exc


async def create_checkout_session(
    db: Session, user_id: int, product_id: str, quantity: int
) -> dict[str, str]:
    product = get_credit_product(product_id)
    if not product:
        raise BadRequestError("Invalid product ID")

    user = db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")

    return_url = settings.dodo_payments_return_url

    from dodopayments import AsyncDodoPayments

    purchase = CreditPurchase(
        user_id=user_id,
        provider=PROVIDER_DODO,
        provider_session_id=PROVIDER_SESSION_PENDING,
        credits_amount=product.credits * quantity,
        status=PURCHASE_STATUS_PENDING,
        product_id=product.product_id,
    )
    db.add(purchase)
    db.commit()
    db.refresh(purchase)

    dodo = AsyncDodoPayments(
        bearer_token=settings.dodo_payments_api_key,
        environment=settings.dodo_payments_environment,
    )

    try:
        session = await dodo.post(
            "/checkouts",
            cast_to=dict[str, object],
            body={
                "product_cart": [
                    {
                        "product_id": product.product_id,
                        "quantity": quantity,
                    }
                ],
                "return_url": return_url,
                "customer": {
                    "email": user.email,
                    "name": user.name or user.email,
                },
                "metadata": {
                    "purchase_id": str(purchase.id),
                    "user_id": str(user.id),
                },
            },
        )
    except Exception:
        purchase.status = PURCHASE_STATUS_FAILED
        db.commit()
        raise

    session_id = session.get("session_id")
    checkout_url = session.get("checkout_url") or session.get("url")
    if not session_id or not checkout_url:
        purchase.status = PURCHASE_STATUS_FAILED
        db.commit()
        raise InternalServerError("Checkout session creation failed")

    purchase.provider_session_id = session_id
    db.commit()

    return {"session_id": session_id, "checkout_url": checkout_url}


def handle_webhook_event(db: Session, payload: dict[str, Any]) -> None:
    event_type = payload.get("type")
    data = payload.get("data", {})

    if event_type not in {
        EVENT_PAYMENT_SUCCEEDED,
        EVENT_PAYMENT_FAILED,
        EVENT_PAYMENT_CANCELLED,
    }:
        return

    payment_id = data.get("payment_id")
    metadata = data.get("metadata") or {}
    purchase_id = metadata.get("purchase_id")
    if not payment_id:
        logger.warning("%s missing payment_id", event_type)
        return

    purchase = None
    if purchase_id:
        purchase = db.get(CreditPurchase, int(purchase_id))
    if not purchase:
        session_id = data.get("checkout_session_id")
        if session_id:
            purchase = (
                db.query(CreditPurchase)
                .filter(CreditPurchase.provider_session_id == session_id)
                .first()
            )
    if not purchase:
        logger.warning("Unable to match purchase", extra={"payment_id": payment_id})
        return

    if purchase.status == PURCHASE_STATUS_COMPLETED:
        return

    if event_type == EVENT_PAYMENT_SUCCEEDED:
        credits_service.grant_purchase_credits(
            db, purchase.user_id, payment_id, purchase.credits_amount
        )
        purchase.status = PURCHASE_STATUS_COMPLETED
        purchase.provider_payment_id = payment_id
        db.commit()
        return

    purchase.status = (
        PURCHASE_STATUS_FAILED
        if event_type == EVENT_PAYMENT_FAILED
        else PURCHASE_STATUS_CANCELLED
    )
    purchase.provider_payment_id = payment_id
    db.commit()


def list_credit_products() -> list[CreditProductRead]:
    products: list[CreditProductRead] = []
    for item in settings.dodo_credit_products:
        price_per_credit = round(item.price_inr / item.credits, 4)
        products.append(
            CreditProductRead(
                product_id=item.product_id,
                credits=item.credits,
                name=item.name or f"{item.credits} Credits",
                price_inr=item.price_inr,
                price_per_credit=price_per_credit,
            )
        )
    return products
