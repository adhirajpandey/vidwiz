import json
import logging
from typing import Any

from sqlalchemy.orm import Session
from standardwebhooks import Webhook, WebhookVerificationError

from src.auth.models import User
from src.config import settings
from src.credits import service as credits_service
from src.exceptions import BadRequestError, InternalServerError, NotFoundError, UnauthorizedError
from src.payments.models import CreditPurchase
from src.payments.products import get_credit_product
from src.payments.schemas import CreditProductRead


logger = logging.getLogger(__name__)


def _require_api_key() -> str:
    if not settings.dodo_payments_api_key:
        raise InternalServerError("Dodo Payments API key not configured")
    return settings.dodo_payments_api_key


def _require_webhook_key() -> str:
    if not settings.dodo_payments_webhook_key:
        raise InternalServerError("Dodo Payments webhook key not configured")
    return settings.dodo_payments_webhook_key


def _require_return_url() -> str:
    if not settings.dodo_payments_return_url:
        raise InternalServerError("Dodo Payments return URL not configured")
    return settings.dodo_payments_return_url


def verify_webhook_signature(payload: bytes, headers: dict[str, str]) -> None:
    secret = _require_webhook_key()
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

    _require_api_key()
    return_url = _require_return_url()

    from dodopayments import AsyncDodoPayments

    purchase = CreditPurchase(
        user_id=user_id,
        provider="dodo",
        provider_session_id="pending",
        credits_amount=product.credits * quantity,
        status="pending",
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
        purchase.status = "failed"
        db.commit()
        raise

    session_id = session.get("session_id")
    checkout_url = session.get("checkout_url") or session.get("url")
    if not session_id or not checkout_url:
        purchase.status = "failed"
        db.commit()
        raise InternalServerError("Checkout session creation failed")

    purchase.provider_session_id = session_id
    db.commit()

    return {"session_id": session_id, "checkout_url": checkout_url}


def handle_webhook_event(db: Session, payload: dict[str, Any]) -> None:
    event_type = payload.get("type")
    data = payload.get("data", {})

    if event_type not in {"payment.succeeded", "payment.failed", "payment.cancelled"}:
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

    if purchase.status == "completed":
        return

    if event_type == "payment.succeeded":
        credits_service.grant_purchase_credits(
            db, purchase.user_id, payment_id, purchase.credits_amount
        )
        purchase.status = "completed"
        purchase.provider_payment_id = payment_id
        db.commit()
        return

    purchase.status = "failed" if event_type == "payment.failed" else "cancelled"
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
