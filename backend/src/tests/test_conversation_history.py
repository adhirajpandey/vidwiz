import pytest

from src import transcripts
from src.conversations import service as conversations_service
from src.conversations.models import Conversation, ConversationScope
from src.tests.test_moments import auth_headers
from src.videos.models import TranscriptStatus, Video


def add_chat(db_session, user, video_id, questions, scope=ConversationScope.VIDEO):
    conversation = Conversation(scope=scope, video_id=video_id, user_id=user.id)
    db_session.add(conversation)
    db_session.flush()
    for question in questions:
        conversations_service.save_chat_message(
            db_session, conversation.id, "user", question
        )
        conversations_service.save_chat_message(
            db_session, conversation.id, "assistant", "answer"
        )
    return conversation


@pytest.fixture
def videos(db_session):
    db_session.add_all(
        [
            Video(video_id="aaaaaaaaaaa", title="Alpha"),
            Video(video_id="bbbbbbbbbbb", title="Beta"),
        ]
    )
    db_session.flush()


@pytest.mark.asyncio
async def test_list_conversations_latest_first_with_filters(
    client, db_session, user, videos
):
    empty = add_chat(db_session, user, "aaaaaaaaaaa", [])
    alpha = add_chat(
        db_session, user, "aaaaaaaaaaa", ["What is " + "very " * 30 + "long?"]
    )
    beta = add_chat(db_session, user, "bbbbbbbbbbb", ["Beta question", "Follow up"])
    library = add_chat(
        db_session, user, None, ["Across everything?"], scope=ConversationScope.LIBRARY
    )
    headers = auth_headers(user)

    listed = (await client.get("/v2/conversations", headers=headers)).json()
    ids = [item["id"] for item in listed["conversations"]]
    assert ids == [library.id, beta.id, alpha.id]
    assert empty.id not in ids
    by_id = {item["id"]: item for item in listed["conversations"]}
    assert by_id[beta.id]["title"] == "Beta question"
    assert by_id[beta.id]["message_count"] == 4
    assert by_id[beta.id]["video_title"] == "Beta"
    assert by_id[alpha.id]["title"].endswith("…")
    assert len(by_id[alpha.id]["title"]) <= 81
    assert by_id[library.id]["scope"] == "library"
    assert by_id[library.id]["video_id"] is None

    for_video = (
        await client.get("/v2/conversations?video_id=bbbbbbbbbbb", headers=headers)
    ).json()
    assert [item["id"] for item in for_video["conversations"]] == [beta.id]

    library_only = (
        await client.get("/v2/conversations?scope=library", headers=headers)
    ).json()
    assert [item["id"] for item in library_only["conversations"]] == [library.id]

    paged = (await client.get("/v2/conversations?per_page=2", headers=headers)).json()
    assert paged["has_more"] is True


@pytest.mark.asyncio
async def test_create_library_conversation_rules(client, user):
    headers = auth_headers(user)

    created = await client.post(
        "/v2/conversations", headers=headers, json={"scope": "library"}
    )
    assert created.status_code == 201
    assert created.json()["scope"] == "library"
    assert created.json()["video_id"] is None

    with_video = await client.post(
        "/v2/conversations",
        headers=headers,
        json={"scope": "library", "video_id": "aaaaaaaaaaa"},
    )
    assert with_video.status_code == 422

    missing_video = await client.post(
        "/v2/conversations", headers=headers, json={"scope": "video"}
    )
    assert missing_video.status_code == 422

    guest = await client.post(
        "/v2/conversations",
        headers={"X-Guest-Session-ID": "guest-1"},
        json={"scope": "library"},
    )
    assert guest.status_code == 401


@pytest.mark.asyncio
async def test_transcript_endpoint_states(client, db_session, user, monkeypatch):
    db_session.add_all(
        [
            Video(
                video_id="aaaaaaaaaaa",
                title="Ready",
                transcript_status=TranscriptStatus.READY,
            ),
            Video(video_id="bbbbbbbbbbb", title="Pending"),
            Video(
                video_id="ccccccccccc",
                title="Failed",
                transcript_status=TranscriptStatus.UNAVAILABLE,
            ),
        ]
    )
    db_session.flush()
    monkeypatch.setattr(
        transcripts,
        "load_transcript",
        lambda _video_id: [
            {"text": "second", "offset": 5, "duration": 2},
            {"text": " first ", "offset": 1, "duration": 3},
            {"text": "", "offset": 9},
        ],
    )
    headers = auth_headers(user)

    ready = (
        await client.get("/v2/videos/aaaaaaaaaaa/transcript", headers=headers)
    ).json()
    pending = (
        await client.get("/v2/videos/bbbbbbbbbbb/transcript", headers=headers)
    ).json()
    failed = (
        await client.get("/v2/videos/ccccccccccc/transcript", headers=headers)
    ).json()
    guest = await client.get(
        "/v2/videos/aaaaaaaaaaa/transcript", headers={"X-Guest-Session-ID": "g"}
    )

    assert ready["status"] == "ready"
    assert ready["segments"] == [
        {"start_seconds": 1.0, "end_seconds": 4.0, "text": "first"},
        {"start_seconds": 5.0, "end_seconds": 7.0, "text": "second"},
    ]
    assert pending == {
        "video_id": "bbbbbbbbbbb",
        "status": "pending",
        "segments": [],
    }
    assert failed["status"] == "unavailable"
    assert guest.status_code == 200
