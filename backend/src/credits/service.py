from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.auth.models import User
from src.credits.models import CreditsLedger
from src.exceptions import ForbiddenError, NotFoundError


SIGNUP_GRANT_AMOUNT = 100
WIZ_CHAT_COST = 5
AI_NOTE_COST = 1

REASON_SIGNUP_GRANT = "signup_grant"
REASON_WIZ_CHAT = "wiz_chat"
REASON_AI_NOTE = "ai_note"
REASON_PURCHASE = "purchase"


def _get_user_or_raise(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError("User not found")
    return user


def _ledger_exists(
    db: Session, user_id: int, reason: str, ref_type: str, ref_id: str
) -> bool:
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
    if _ledger_exists(db, user.id, REASON_SIGNUP_GRANT, "user", str(user.id)):
        return
    _apply_ledger(
        db,
        user,
        SIGNUP_GRANT_AMOUNT,
        REASON_SIGNUP_GRANT,
        "user",
        str(user.id),
    )


def charge_wiz_chat_for_video(db: Session, user_id: int, video_id: str) -> bool:
    if _ledger_exists(db, user_id, REASON_WIZ_CHAT, "video", video_id):
        return False

    user = _get_user_or_raise(db, user_id)
    if user.credits_balance < WIZ_CHAT_COST:
        raise ForbiddenError(
            "Insufficient credits",
            details={"required": WIZ_CHAT_COST, "available": user.credits_balance},
        )

    _apply_ledger(db, user, -WIZ_CHAT_COST, REASON_WIZ_CHAT, "video", video_id)
    return True


def charge_ai_note_enqueue(db: Session, user_id: int, note_id: int) -> None:
    if _ledger_exists(db, user_id, REASON_AI_NOTE, "note", str(note_id)):
        return

    user = _get_user_or_raise(db, user_id)
    if user.credits_balance < AI_NOTE_COST:
        raise ForbiddenError(
            "Insufficient credits",
            details={"required": AI_NOTE_COST, "available": user.credits_balance},
        )

    _apply_ledger(db, user, -AI_NOTE_COST, REASON_AI_NOTE, "note", str(note_id))


def grant_purchase_credits(
    db: Session, user_id: int, payment_id: str, credits_amount: int
) -> None:
    if _ledger_exists(db, user_id, REASON_PURCHASE, "payment", payment_id):
        return

    user = _get_user_or_raise(db, user_id)
    _apply_ledger(db, user, credits_amount, REASON_PURCHASE, "payment", payment_id)
