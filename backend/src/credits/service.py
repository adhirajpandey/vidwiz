import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.auth.models import User
from src.config import settings
from src.credits.models import CreditsLedger
from src.exceptions import ForbiddenError, NotFoundError

REASON_SIGNUP_GRANT = "signup_grant"
REASON_WIZ_CHAT = "wiz_chat"
REASON_AI_NOTE = "ai_note"
REASON_PURCHASE = "purchase"

logger = logging.getLogger(__name__)


def _get_user_or_raise(db: Session, user_id: int) -> User:
    logger.debug("Fetching user for credits", extra={"user_id": user_id})
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")
    return user


def _ledger_exists(
    db: Session, user_id: int, reason: str, ref_type: str, ref_id: str
) -> bool:
    logger.debug(
        "Checking ledger entry",
        extra={"user_id": user_id, "reason": reason, "ref_type": ref_type, "ref_id": ref_id},
    )
    query = (
        select(CreditsLedger.id)
        .where(
            CreditsLedger.user_id == user_id,
            CreditsLedger.reason == reason,
            CreditsLedger.ref_type == ref_type,
            CreditsLedger.ref_id == ref_id,
        )
        .limit(1)
    )
    return db.execute(query).scalar_one_or_none() is not None


def _apply_ledger(
    db: Session,
    user: User,
    delta: int,
    reason: str,
    ref_type: str,
    ref_id: str,
) -> None:
    logger.debug(
        "Applying ledger entry",
        extra={"user_id": user.id, "delta": delta, "reason": reason, "ref_type": ref_type},
    )
    entry = CreditsLedger(
        user_id=user.id,
        delta=delta,
        reason=reason,
        ref_type=ref_type,
        ref_id=ref_id,
    )
    user.credits_balance += delta
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        db.refresh(user)


def grant_signup_credits(db: Session, user: User) -> None:
    logger.debug("Granting signup credits", extra={"user_id": user.id})
    if _ledger_exists(db, user.id, REASON_SIGNUP_GRANT, "user", str(user.id)):
        return
    _apply_ledger(
        db,
        user,
        settings.signup_grant_amount,
        REASON_SIGNUP_GRANT,
        "user",
        str(user.id),
    )


def charge_wiz_chat_for_video(db: Session, user_id: int, video_id: str) -> bool:
    logger.debug(
        "Charging wiz chat", extra={"user_id": user_id, "video_id": video_id}
    )
    if _ledger_exists(db, user_id, REASON_WIZ_CHAT, "video", video_id):
        return False

    user = _get_user_or_raise(db, user_id)
    if user.credits_balance < settings.wiz_chat_cost:
        raise ForbiddenError(
            "Insufficient credits",
            details={
                "required": settings.wiz_chat_cost,
                "available": user.credits_balance,
            },
        )

    _apply_ledger(
        db, user, -settings.wiz_chat_cost, REASON_WIZ_CHAT, "video", video_id
    )
    return True


def charge_ai_note_enqueue(db: Session, user_id: int, note_id: int) -> None:
    logger.debug(
        "Charging AI note enqueue", extra={"user_id": user_id, "note_id": note_id}
    )
    if _ledger_exists(db, user_id, REASON_AI_NOTE, "note", str(note_id)):
        return

    user = _get_user_or_raise(db, user_id)
    if user.credits_balance < settings.ai_note_cost:
        raise ForbiddenError(
            "Insufficient credits",
            details={
                "required": settings.ai_note_cost,
                "available": user.credits_balance,
            },
        )

    _apply_ledger(
        db, user, -settings.ai_note_cost, REASON_AI_NOTE, "note", str(note_id)
    )


def grant_purchase_credits(
    db: Session, user_id: int, payment_id: str, credits_amount: int
) -> None:
    logger.debug(
        "Granting purchase credits",
        extra={"user_id": user_id, "payment_id": payment_id, "credits": credits_amount},
    )
    if _ledger_exists(db, user_id, REASON_PURCHASE, "payment", payment_id):
        return

    user = _get_user_or_raise(db, user_id)
    _apply_ledger(db, user, credits_amount, REASON_PURCHASE, "payment", payment_id)
