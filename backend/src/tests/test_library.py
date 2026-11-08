from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, event, func, insert, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from src.conversations import service as conversations_service
from src.conversations.models import Conversation, ConversationScope, Message
from src.credits import service as credits_service
from src.library import service as library_service
from src.library.models import LibraryItem
from src.moments import service as moments_service
from src.moments.models import Moment
from src.moments.schemas import CaptureCreate
from src.tests.test_moments import auth_headers
from src.videos.models import Video


def add_video(db_session, user, video_id, title, added_days_ago=0):
    db_session.add(Video(video_id=video_id, title=title))
    db_session.flush()
    db_session.add(
        LibraryItem(
            user_id=user.id,
            video_id=video_id,
            added_at=datetime.now(timezone.utc) - timedelta(days=added_days_ago),
        )
    )
    db_session.flush()


@pytest.mark.asyncio
async def test_library_lists_counts_sorts_and_searches(client, db_session, user):
    add_video(db_session, user, "aaaaaaaaaaa", "Alpha talk", added_days_ago=3)
    add_video(db_session, user, "bbbbbbbbbbb", "Beta talk", added_days_ago=2)
    moments_service.capture(
        db_session,
        user.id,
        CaptureCreate(video="aaaaaaaaaaa", at=5, ai=False),
        lambda *_: None,
    )
    moments_service.capture(
        db_session,
        user.id,
        CaptureCreate(video="aaaaaaaaaaa", at=50, ai=False),
        lambda *_: None,
    )
    headers = auth_headers(user)

    by_activity = (await client.get("/v2/library", headers=headers)).json()
    assert [video["video_id"] for video in by_activity["videos"]] == [
        "aaaaaaaaaaa",
        "bbbbbbbbbbb",
    ]
    assert by_activity["videos"][0]["moment_count"] == 2
    assert by_activity["videos"][1]["moment_count"] == 0
    assert by_activity["total"] == 2

    by_added = (await client.get("/v2/library?sort=added_desc", headers=headers)).json()
    assert by_added["videos"][0]["video_id"] == "bbbbbbbbbbb"

    searched = (await client.get("/v2/library?q=beta", headers=headers)).json()
    assert [video["video_id"] for video in searched["videos"]] == ["bbbbbbbbbbb"]

    paged = (await client.get("/v2/library?per_page=1&page=2", headers=headers)).json()
    assert paged["total_pages"] == 2
    assert len(paged["videos"]) == 1


def test_title_sorts_put_untitled_videos_last(db_session, user):
    from src.library.schemas import LibraryParams

    add_video(db_session, user, "aaaaaaaaaaa", "Alpha")
    add_video(db_session, user, "bbbbbbbbbbb", None)
    add_video(db_session, user, "ccccccccccc", "Gamma")

    for sort, expected in [
        ("title_asc", ["aaaaaaaaaaa", "ccccccccccc", "bbbbbbbbbbb"]),
        ("title_desc", ["ccccccccccc", "aaaaaaaaaaa", "bbbbbbbbbbb"]),
    ]:
        response = library_service.list_library(
            db_session, user.id, LibraryParams(sort=sort)
        )
        assert [video.video_id for video in response.videos] == expected


@pytest.mark.asyncio
async def test_library_save_and_remove(client, db_session, user):
    headers = auth_headers(user)

    saved = await client.put("/v2/library/ccccccccccc", headers=headers)
    again = await client.put("/v2/library/ccccccccccc", headers=headers)

    assert saved.status_code == 200
    assert again.status_code == 200
    assert db_session.get(LibraryItem, (user.id, "ccccccccccc")) is not None

    removed = await client.delete("/v2/library/ccccccccccc", headers=headers)
    missing = await client.delete("/v2/library/ccccccccccc", headers=headers)
    assert removed.status_code == 200
    assert missing.status_code == 404


def _seed_video_activity(db_session, owner, video_id):
    moments_service.capture(
        db_session,
        owner.id,
        CaptureCreate(video=video_id, at=5, ai=False),
        lambda *_: None,
    )
    conversation = conversations_service.create_conversation(
        db_session, video_id, owner.id, None
    )
    db_session.add(
        Message(conversation_id=conversation.id, role="user", content="Question")
    )
    db_session.commit()


def _activity_counts(db_session, owner_id):
    db_session.expire_all()
    moments = db_session.scalar(
        select(func.count()).select_from(Moment).where(Moment.user_id == owner_id)
    )
    chats = db_session.scalar(
        select(func.count())
        .select_from(Conversation)
        .where(Conversation.user_id == owner_id)
    )
    messages = db_session.scalar(
        select(func.count())
        .select_from(Message)
        .join(Conversation)
        .where(Conversation.user_id == owner_id)
    )
    return moments, chats, messages


@pytest.mark.asyncio
async def test_remove_deletes_only_this_users_data_for_the_video(
    client, db_session, user
):
    from src.auth import service as auth_service

    other = auth_service.create_user(db_session, "o@example.com", "Other", "pw123456")
    add_video(db_session, user, "eeeeeeeeeee", "Removed")
    add_video(db_session, user, "fffffffffff", "Kept")
    _seed_video_activity(db_session, user, "eeeeeeeeeee")
    _seed_video_activity(db_session, user, "fffffffffff")
    _seed_video_activity(db_session, other, "eeeeeeeeeee")
    library_chat = conversations_service.create_conversation(
        db_session, None, user.id, None, ConversationScope.LIBRARY
    )
    credits_service.charge_wiz_chat_for_video(db_session, user.id, "eeeeeeeeeee")

    response = await client.delete(
        "/v2/library/eeeeeeeeeee", headers=auth_headers(user)
    )

    assert response.status_code == 200
    # One moment, one video chat with its message, and the library chat remain.
    assert _activity_counts(db_session, user.id) == (1, 2, 1)
    assert db_session.get(Conversation, library_chat.id) is not None
    assert db_session.get(LibraryItem, (user.id, "eeeeeeeeeee")) is None
    assert db_session.get(LibraryItem, (user.id, "fffffffffff")) is not None
    # Another user's copy and the shared video are untouched.
    assert _activity_counts(db_session, other.id) == (1, 1, 1)
    assert db_session.get(LibraryItem, (other.id, "eeeeeeeeeee")) is not None
    assert db_session.scalar(select(Video).where(Video.video_id == "eeeeeeeeeee"))
    assert credits_service.wiz_chat_unlocked(db_session, user.id, "eeeeeeeeeee")


def test_remove_survives_a_message_arriving_mid_delete(engine):
    """Uses real commits: the race needs a second connection to see the chat."""
    from src.auth import service as auth_service

    make_session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    video_id = "ggggggggggg"
    with make_session() as db:
        owner = auth_service.create_user(db, "race@example.com", "Race", "pw123456")
        user_id = owner.id
        db.add(Video(video_id=video_id, title="Race"))
        db.flush()
        db.add(LibraryItem(user_id=user_id, video_id=video_id))
        conversation = Conversation(video_id=video_id, user_id=user_id)
        db.add(conversation)
        db.flush()
        conversation_id = conversation.id
        db.add(Message(conversation_id=conversation_id, role="user", content="First"))
        db.commit()

    fired = []

    def send_message_mid_delete(_conn, _cursor, statement, *_):
        if fired or not statement.startswith("DELETE FROM conversations"):
            return
        fired.append(True)
        with engine.connect() as other:
            other.execute(text("SET LOCAL lock_timeout = '200ms'"))
            try:
                other.execute(
                    insert(Message).values(
                        conversation_id=conversation_id, role="user", content="Late"
                    )
                )
                other.commit()
            except OperationalError:
                # The delete holds the chat, so this write waits and gives up.
                other.rollback()

    event.listen(engine, "before_cursor_execute", send_message_mid_delete)
    try:
        with make_session() as db:
            assert library_service.remove_video(db, user_id, video_id) is True
        assert fired
        with make_session() as db:
            assert db.get(Conversation, conversation_id) is None
            assert db.get(LibraryItem, (user_id, video_id)) is None
    finally:
        event.remove(engine, "before_cursor_execute", send_message_mid_delete)
        with engine.begin() as connection:
            connection.execute(
                delete(Message).where(Message.conversation_id == conversation_id)
            )
            connection.execute(
                delete(Conversation).where(Conversation.id == conversation_id)
            )
            connection.execute(
                delete(LibraryItem).where(LibraryItem.user_id == user_id)
            )
            connection.execute(delete(Video).where(Video.video_id == video_id))
            connection.execute(
                text("DELETE FROM credits_ledger WHERE user_id = :u"), {"u": user_id}
            )
            connection.execute(text("DELETE FROM users WHERE id = :u"), {"u": user_id})


def test_library_is_per_user(db_session, user):
    from src.auth import service as auth_service
    from src.library.schemas import LibraryParams

    other = auth_service.create_user(db_session, "o@example.com", "Other", "pw123456")
    add_video(db_session, other, "ddddddddddd", "Theirs")

    response = library_service.list_library(db_session, user.id, LibraryParams())

    assert response.videos == []


def test_asking_about_a_video_saves_it(db_session, user):
    db_session.add(Video(video_id="eeeeeeeeeee", title="Asked"))
    db_session.flush()
    conversation = Conversation(video_id="eeeeeeeeeee", user_id=user.id)
    db_session.add(conversation)
    db_session.flush()

    conversations_service.save_chat_message(
        db_session, conversation.id, "assistant", "hello"
    )
    assert db_session.get(LibraryItem, (user.id, "eeeeeeeeeee")) is None

    conversations_service.save_chat_message(
        db_session, conversation.id, "user", "what is this about?"
    )
    assert db_session.get(LibraryItem, (user.id, "eeeeeeeeeee")) is not None


@pytest.mark.asyncio
async def test_api_token_routes(client, user):
    headers = auth_headers(user)

    created = await client.post(
        "/v2/auth/tokens", headers=headers, json={"name": " Phone "}
    )
    assert created.status_code == 201
    token = created.json()["token"]
    assert token.startswith("vw_")
    assert created.json()["name"] == "Phone"
    assert created.json()["token_hint"] == token[-4:]

    listed = (await client.get("/v2/auth/tokens", headers=headers)).json()
    assert [item["name"] for item in listed] == ["Phone"]
    assert "token" not in listed[0]

    # API tokens cannot use session-only endpoints.
    denied = await client.get(
        "/v2/auth/tokens", headers={"Authorization": f"Bearer {token}"}
    )
    assert denied.status_code == 401

    token_id = created.json()["id"]
    revoked = await client.delete(f"/v2/auth/tokens/{token_id}", headers=headers)
    assert revoked.status_code == 200
    assert (await client.get("/v2/auth/tokens", headers=headers)).json() == []
    again = await client.delete(f"/v2/auth/tokens/{token_id}", headers=headers)
    assert again.status_code == 404


@pytest.mark.asyncio
async def test_library_views_counts_and_latest_preview(client, db_session, user):
    from src.auth import service as auth_service
    from src.conversations.models import Message
    from src.moments.models import CaptureSource, Moment

    other = auth_service.create_user(
        db_session, "other@example.com", "Other", "pw123456"
    )
    for video_id, title in [
        ("aaaaaaaaaaa", "Alpha"),
        ("bbbbbbbbbbb", "Beta"),
        ("ccccccccccc", "Gamma"),
    ]:
        add_video(db_session, user, video_id, title)
    a = db_session.query(Video).filter_by(video_id="aaaaaaaaaaa").one()
    a.video_metadata = {"uploader": "Useful_Channel%"}
    old = datetime.now(timezone.utc) - timedelta(days=2)
    db_session.add_all(
        [
            Moment(
                user_id=user.id,
                video_id="aaaaaaaaaaa",
                at_seconds=1,
                note="Older note",
                source=CaptureSource.WEB,
                created_at=old,
            ),
            Moment(
                user_id=user.id,
                video_id="aaaaaaaaaaa",
                at_seconds=20,
                quote="Latest quote",
                source=CaptureSource.WEB,
            ),
            Moment(
                user_id=other.id,
                video_id="aaaaaaaaaaa",
                at_seconds=40,
                note="Private note",
                source=CaptureSource.WEB,
            ),
        ]
    )
    for video_id, owner, roles in [
        ("bbbbbbbbbbb", user.id, ["user", "assistant", "user"]),
        ("bbbbbbbbbbb", user.id, ["user"]),
        ("aaaaaaaaaaa", user.id, []),
        ("ccccccccccc", user.id, ["assistant"]),
        ("aaaaaaaaaaa", other.id, ["user"]),
    ]:
        chat = Conversation(video_id=video_id, user_id=owner)
        db_session.add(chat)
        db_session.flush()
        db_session.add_all(
            [
                Message(conversation_id=chat.id, role=role, content="hello")
                for role in roles
            ]
        )
    db_session.flush()
    headers = auth_headers(user)
    result = (await client.get("/v2/library?sort=moments_desc", headers=headers)).json()
    assert result["counts"] == {"all": 3, "with_moments": 1, "with_chats": 1}
    assert result["videos"][0]["moment_count"] == 2
    assert result["videos"][0]["chat_count"] == 0
    assert result["videos"][0]["latest_moment"] == {
        "text": "Latest quote",
        "kind": "quote",
    }
    chats = (await client.get("/v2/library?sort=chats_desc", headers=headers)).json()
    assert chats["videos"][0]["video_id"] == "bbbbbbbbbbb"
    assert chats["videos"][0]["chat_count"] == 2  # Conversations, not questions.
    for view, video_id in [
        ("with_moments", "aaaaaaaaaaa"),
        ("with_chats", "bbbbbbbbbbb"),
    ]:
        filtered = (
            await client.get(f"/v2/library?view={view}&per_page=1", headers=headers)
        ).json()
        assert filtered["total"] == filtered["total_pages"] == 1
        assert filtered["videos"][0]["video_id"] == video_id
        assert filtered["counts"] == result["counts"]
    for query in ["Useful_Channel%", "aaaaaaaaaaa"]:
        matched = (
            await client.get("/v2/library", params={"q": query}, headers=headers)
        ).json()
        assert [v["video_id"] for v in matched["videos"]] == ["aaaaaaaaaaa"]
        assert matched["counts"] == {"all": 1, "with_moments": 1, "with_chats": 0}
    assert (
        await client.get("/v2/library", params={"q": "%_"}, headers=headers)
    ).json()["total"] == 0
    assert (
        await client.get("/v2/library?view=unknown", headers=headers)
    ).status_code == 422


def test_exact_video_id_leads_matches_for_link_membership(db_session, user):
    from src.library.schemas import LibraryParams

    add_video(db_session, user, "aaaaaaaaaaa", "Saved video", added_days_ago=5)
    add_video(db_session, user, "bbbbbbbbbbb", "A video mentioning aaaaaaaaaaa")
    result = library_service.list_library(
        db_session, user.id, LibraryParams(q="aaaaaaaaaaa", per_page=1)
    )
    assert result.total == 2
    assert result.videos[0].video_id == "aaaaaaaaaaa"
