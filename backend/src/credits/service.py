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
REASON_AI_MOMENT = "ai_moment"
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
        extra={
            "user_id": user_id,
            "reason": reason,
            "ref_type": ref_type,
            "ref_id": ref_id,
        },
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


def _apply_once(
    db: Session,
    user_id: int,
    delta: int,
    reason: str,
    ref_type: str,
    ref_id: str,
) -> bool:
    """Apply one ledger entry per reference; charges require enough balance."""
    if _ledger_exists(db, user_id, reason, ref_type, ref_id):
        return False

    user = _get_user_or_raise(db, user_id)
    if delta < 0 and user.credits_balance < -delta:
        raise ForbiddenError(
            "Insufficient credits",
            details={"required": -delta, "available": user.credits_balance},
        )

    logger.debug(
        "Applying ledger entry",
        extra={
            "user_id": user.id,
            "delta": delta,
            "reason": reason,
            "ref_type": ref_type,
        },
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
    return True


def grant_signup_credits(db: Session, user: User) -> None:
    logger.debug("Granting signup credits", extra={"user_id": user.id})
    _apply_once(
        db,
        user.id,
        settings.signup_grant_amount,
        REASON_SIGNUP_GRANT,
        "user",
        str(user.id),
    )


def wiz_chat_unlocked(db: Session, user_id: int, video_id: str) -> bool:
    return _ledger_exists(db, user_id, REASON_WIZ_CHAT, "video", video_id)


def charge_wiz_chat_for_video(db: Session, user_id: int, video_id: str) -> bool:
    logger.debug("Charging wiz chat", extra={"user_id": user_id, "video_id": video_id})
    return _apply_once(
        db, user_id, -settings.wiz_chat_cost, REASON_WIZ_CHAT, "video", video_id
    )


def charge_ai_moment(db: Session, user_id: int, moment_id: int) -> None:
    """Charge one AI line per moment; repeat requests are free."""
    logger.debug(
        "Charging AI moment", extra={"user_id": user_id, "moment_id": moment_id}
    )
    _apply_once(
        db,
        user_id,
        -settings.ai_moment_cost,
        REASON_AI_MOMENT,
        "moment",
        str(moment_id),
    )


def grant_purchase_credits(
    db: Session, user_id: int, payment_id: str, credits_amount: int
) -> None:
    logger.debug(
        "Granting purchase credits",
        extra={"user_id": user_id, "payment_id": payment_id, "credits": credits_amount},
    )
    _apply_once(db, user_id, credits_amount, REASON_PURCHASE, "payment", payment_id)
