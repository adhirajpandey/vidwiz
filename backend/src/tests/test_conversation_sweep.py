import threading
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, insert, select, update
from sqlalchemy.orm import Session

from src.auth import service as auth_service
from src.config import settings
from src.conversations import service as conversations_service
from src.conversations.models import Conversation, ConversationScope, Message
from src.credits import service as credits_service
from src.videos.models import Video

VIDEO_ID = "abc123DEF45"
CUTOFF = timedelta(days=7)


def age(db_session, conversation_id: int, days: int) -> None:
    db_session.execute(
        update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(created_at=datetime.now(timezone.utc) - timedelta(days=days))
    )
    db_session.commit()


def conversation(db_session, **values) -> Conversation:
    row = Conversation(**{"video_id": VIDEO_ID, **values})
    db_session.add(row)
    db_session.commit()
    return row


def test_sweep_deletes_only_old_conversations_without_messages(db_session, user):
    db_session.add(Video(video_id=VIDEO_ID, title="Video"))
    old_empty = conversation(db_session, user_id=user.id)
    old_guest = conversation(db_session, guest_session_id="guest-1")
    old_library = conversation(
        db_session, user_id=user.id, scope=ConversationScope.LIBRARY, video_id=None
    )
    recent_empty = conversation(db_session, user_id=user.id)
    asked = conversation(db_session, user_id=user.id)
    answered_only = conversation(db_session, guest_session_id="guest-2")
    conversations_service.save_chat_message(
        db_session, asked.id, conversations_service.DB_ROLE_USER, "What is this?"
    )
    conversations_service.save_chat_message(
        db_session, answered_only.id, conversations_service.DB_ROLE_ASSISTANT, "Hi"
    )
    ids = [old_empty.id, old_guest.id, old_library.id, asked.id, answered_only.id]
    for conversation_id in ids:
        age(db_session, conversation_id, days=30)
    age(db_session, recent_empty.id, days=6)

    assert conversations_service.sweep_empty(db_session, CUTOFF) == 3

    remaining = set(db_session.execute(select(Conversation.id)).scalars())
    assert remaining == {recent_empty.id, asked.id, answered_only.id}
    assert conversations_service.list_messages(db_session, asked.id)


@pytest.mark.asyncio
async def test_swept_paid_video_chat_stays_unlocked_without_a_new_charge(
    client, db_session
):
    user = auth_service.create_user(
        db_session, "paid@example.com", "Paid", "password123"
    )
    user.credits_balance = 10
    db_session.commit()
    headers = {
        "Authorization": f"Bearer {auth_service.generate_jwt_token(user, settings.secret_key, 1)}"
    }

    first = await client.post(
        "/v2/conversations", headers=headers, json={"video_id": VIDEO_ID}
    )
    assert first.status_code == 201
    db_session.refresh(user)
    assert user.credits_balance == 10 - settings.wiz_chat_cost

    age(db_session, first.json()["id"], days=30)
    assert conversations_service.sweep_empty(db_session, CUTOFF) == 1
    assert credits_service.wiz_chat_unlocked(db_session, user.id, VIDEO_ID)

    again = await client.post(
        "/v2/conversations", headers=headers, json={"video_id": VIDEO_ID}
    )
    assert again.status_code == 201
    db_session.refresh(user)
    assert user.credits_balance == 10 - settings.wiz_chat_cost


@pytest.mark.asyncio
async def test_guest_landing_conversation_survives_until_old(client, db_session):
    headers = {"X-Guest-Session-ID": "guest-landing"}
    created = await client.post(
        "/v2/conversations", headers=headers, json={"video_id": VIDEO_ID}
    )
    conversation_id = created.json()["id"]

    assert conversations_service.sweep_empty(db_session, CUTOFF) == 0
    opened = await client.get(f"/v2/conversations/{conversation_id}", headers=headers)
    assert opened.status_code == 200

    age(db_session, conversation_id, days=30)
    assert conversations_service.sweep_empty(db_session, CUTOFF) == 1
    gone = await client.get(f"/v2/conversations/{conversation_id}", headers=headers)
    assert gone.status_code == 404


def test_sweep_keeps_a_conversation_whose_first_message_is_being_saved(engine):
    """A first message saved during the sweep keeps its conversation.

    This uses committed rows on separate connections, so it cleans up after
    itself instead of relying on the per-test rollback.
    """
    with engine.begin() as connection:
        conversation_id = connection.execute(
            insert(Conversation)
            .values(
                video_id=VIDEO_ID,
                guest_session_id="guest-race",
                created_at=datetime.now(timezone.utc) - timedelta(days=30),
            )
            .returning(Conversation.id)
        ).scalar_one()
    sender = Session(engine)
    sweeper = Session(engine)
    result: dict[str, int] = {}
    try:
        sender.add(
            Message(conversation_id=conversation_id, role="user", content="Hello")
        )
        # The insert holds a key lock on the conversation until it commits.
        sender.flush()
        sweep = threading.Thread(
            target=lambda: result.update(
                deleted=conversations_service.sweep_empty(sweeper, CUTOFF)
            )
        )
        sweep.start()
        sweep.join(timeout=1)
        assert sweep.is_alive(), "the sweep should wait for the message to commit"
        sender.commit()
        sweep.join(timeout=10)

        assert result == {"deleted": 0}
        with engine.connect() as connection:
            messages = connection.execute(
                select(Message.content).where(
                    Message.conversation_id == conversation_id
                )
            ).all()
        assert [row.content for row in messages] == ["Hello"]
    finally:
        sender.close()
        sweeper.close()
        with engine.begin() as connection:
            connection.execute(
                delete(Message).where(Message.conversation_id == conversation_id)
            )
            connection.execute(
                delete(Conversation).where(Conversation.id == conversation_id)
            )
