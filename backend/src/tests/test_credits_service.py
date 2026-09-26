import pytest

from src.auth.models import User
from src.credits import service as credits_service
from src.exceptions import ForbiddenError


def _user(db_session, balance: int) -> User:
    user = User(email="credits@example.com", credits_balance=balance)
    db_session.add(user)
    db_session.commit()
    return user


def test_charges_once_per_reference(db_session):
    user = _user(db_session, 10)

    assert credits_service.charge_wiz_chat_for_video(db_session, user.id, "vid") is True
    assert (
        credits_service.charge_wiz_chat_for_video(db_session, user.id, "vid") is False
    )
    assert user.credits_balance == 5


def test_charge_requires_enough_balance(db_session):
    user = _user(db_session, 0)

    with pytest.raises(ForbiddenError) as error:
        credits_service.charge_ai_note_enqueue(db_session, user.id, 1)
    assert error.value.details == {"required": 1, "available": 0}


def test_purchase_grant_is_idempotent(db_session):
    user = _user(db_session, 0)

    credits_service.grant_purchase_credits(db_session, user.id, "pay_1", 200)
    credits_service.grant_purchase_credits(db_session, user.id, "pay_1", 200)
    assert user.credits_balance == 200
