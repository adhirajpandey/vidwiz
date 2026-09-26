import pytest

from src.auth.models import User
from src.internal import scheduling as internal_scheduling
from src.exceptions import ForbiddenError, InternalServerError, NotFoundError
from src.notes import service as notes_service
from src.notes.models import Note
from src.videos.models import Video


def test_create_note_triggers_ai_when_enabled_and_ready(db_session, monkeypatch):
    user = User(
        email="ai@example.com",
        name="AI User",
        profile_data={"ai_notes_enabled": True},
        credits_balance=1,
    )
    video = Video(video_id="ai123456789", title="AI Video", transcript_available=True)
    db_session.add_all([user, video])
    db_session.commit()

    called = {"count": 0}

    def fake_push(note):
        called["count"] += 1

    monkeypatch.setattr(notes_service, "push_note_to_sqs", fake_push)

    note = notes_service.create_note_for_user(
        db_session, video.video_id, "00:01", None, user.id
    )
    assert note.id is not None
    assert called["count"] == 1


def test_create_note_blocks_ai_when_insufficient_credits(db_session):
    user = User(
        email="ai-block@example.com",
        name="AI Block",
        profile_data={"ai_notes_enabled": True},
        credits_balance=0,
    )
    video = Video(video_id="ai523456789", title="AI Video", transcript_available=True)
    db_session.add_all([user, video])
    db_session.commit()

    with pytest.raises(ForbiddenError) as exc_info:
        notes_service.create_note_for_user(
            db_session, video.video_id, "00:01", None, user.id
        )
    assert "Insufficient credits" in str(exc_info.value)


def test_create_note_does_not_trigger_ai_when_text_present(db_session, monkeypatch):
    user = User(
        email="ai-text@example.com",
        name="AI Text",
        profile_data={"ai_notes_enabled": True},
    )
    video = Video(video_id="ai223456789", title="AI Video", transcript_available=True)
    db_session.add_all([user, video])
    db_session.commit()

    monkeypatch.setattr(notes_service, "push_note_to_sqs", lambda note: pytest.fail())

    note = notes_service.create_note_for_user(
        db_session, video.video_id, "00:01", "hello", user.id
    )
    assert note.text == "hello"


def test_create_note_does_not_trigger_ai_when_disabled(db_session, monkeypatch):
    user = User(
        email="ai-off@example.com",
        name="AI Off",
        profile_data={"ai_notes_enabled": False},
    )
    video = Video(video_id="ai323456789", title="AI Video", transcript_available=True)
    db_session.add_all([user, video])
    db_session.commit()

    monkeypatch.setattr(notes_service, "push_note_to_sqs", lambda note: pytest.fail())

    notes_service.create_note_for_user(
        db_session, video.video_id, "00:01", None, user.id
    )


def test_create_note_does_not_trigger_ai_when_transcript_missing(
    db_session, monkeypatch
):
    user = User(
        email="ai-no-tx@example.com",
        name="AI No TX",
        profile_data={"ai_notes_enabled": True},
    )
    video = Video(video_id="ai423456789", title="AI Video", transcript_available=False)
    db_session.add_all([user, video])
    db_session.commit()

    monkeypatch.setattr(notes_service, "push_note_to_sqs", lambda note: pytest.fail())

    notes_service.create_note_for_user(
        db_session, video.video_id, "00:01", None, user.id
    )


def test_create_note_for_video_title_uses_resolved_result(db_session, monkeypatch):
    user = User(email="title@example.com", name="Title User", profile_data={})
    db_session.add(user)
    db_session.commit()

    monkeypatch.setattr(
        notes_service,
        "resolve_video_by_title",
        lambda video_title: ("resolved12345", "Resolved Title"),
    )

    note = notes_service.create_note_for_video_title(
        db_session,
        "Search Title",
        "00:01",
        "hello",
        user.id,
    )

    assert note.video_id == "resolved12345"
    video = notes_service.videos_service.get_video_by_id(db_session, "resolved12345")
    assert video is not None
    assert video.title == "Resolved Title"


def test_create_note_for_video_title_preserves_ai_enqueue_behavior(
    db_session, monkeypatch
):
    user = User(
        email="title-ai@example.com",
        name="Title AI User",
        profile_data={"ai_notes_enabled": True},
        credits_balance=1,
    )
    db_session.add(user)
    db_session.commit()

    monkeypatch.setattr(
        notes_service,
        "resolve_video_by_title",
        lambda video_title: ("resolvedAI123", "Resolved AI Title"),
    )

    scheduled = {"count": 0}

    def fake_schedule(_db, video):
        video.transcript_available = True

    def fake_push(note):
        scheduled["count"] += 1

    monkeypatch.setattr(internal_scheduling, "schedule_video_tasks", fake_schedule)
    monkeypatch.setattr(notes_service, "push_note_to_sqs", fake_push)

    note = notes_service.create_note_for_video_title(
        db_session,
        "Search Title",
        "00:01",
        None,
        user.id,
    )

    assert note.video_id == "resolvedAI123"
    assert scheduled["count"] == 1


class FakeSearchResponse:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error:
            raise self.error

    def json(self):
        return self.payload


def _fake_search(monkeypatch, response, captured=None):
    def fake_get(url, **kwargs):
        if captured is not None:
            captured.update(url=url, **kwargs)
        return response

    monkeypatch.setattr(notes_service.requests, "get", fake_get)


def _search_result(title):
    return {
        "items": [{"id": {"videoId": "resolved12345"}, "snippet": {"title": title}}]
    }


def test_resolve_video_by_title_returns_top_result(monkeypatch):
    captured = {}
    _fake_search(
        monkeypatch, FakeSearchResponse(_search_result("Resolved Title")), captured
    )

    video_id, title = notes_service.resolve_video_by_title("Search Title")

    assert video_id == "resolved12345"
    assert title == "Resolved Title"
    assert captured["url"] == "https://www.googleapis.com/youtube/v3/search"
    assert captured["params"] == {
        "q": "Search Title",
        "part": "snippet",
        "type": "video",
        "maxResults": 1,
    }
    assert captured["headers"] == {"X-Goog-Api-Key": "test-youtube-data-api-key"}
    assert captured["timeout"] == 10


def test_resolve_video_by_title_decodes_html_entities(monkeypatch):
    _fake_search(
        monkeypatch,
        FakeSearchResponse(_search_result("The Privacy Iceberg (I&#39;m deep)")),
    )

    video_id, title = notes_service.resolve_video_by_title("Privacy Iceberg")

    assert video_id == "resolved12345"
    assert title == "The Privacy Iceberg (I'm deep)"


def test_resolve_video_by_title_raises_not_found_for_empty_results(monkeypatch):
    _fake_search(monkeypatch, FakeSearchResponse({"items": []}))

    with pytest.raises(NotFoundError):
        notes_service.resolve_video_by_title("Missing Video")


def test_resolve_video_by_title_raises_internal_error_for_search_failures(monkeypatch):
    _fake_search(
        monkeypatch,
        FakeSearchResponse(error=notes_service.requests.HTTPError("403 Forbidden")),
    )

    with pytest.raises(InternalServerError):
        notes_service.resolve_video_by_title("Exploding Search")


def test_resolve_video_by_title_requires_api_key(monkeypatch):
    monkeypatch.setattr(notes_service.settings, "youtube_data_api_key", None)

    with pytest.raises(InternalServerError):
        notes_service.resolve_video_by_title("Any Title")


def test_update_note_does_not_trigger_ai_on_update(db_session, monkeypatch):
    video = Video(video_id="ai623456789", title="AI Video", transcript_available=True)
    note = Note(video_id=video.video_id, timestamp="00:01", text=None, user_id=1)
    db_session.add_all([video, note])
    db_session.commit()
    db_session.refresh(note)

    monkeypatch.setattr(notes_service, "push_note_to_sqs", lambda note: pytest.fail())

    notes_service.update_note(db_session, note, text=None, generated_by_ai=True)


def test_list_notes_for_video_orders_by_created_at(db_session):
    video = Video(video_id="noteorder12", title="Order")
    db_session.add(video)
    db_session.commit()

    note1 = Note(video_id=video.video_id, timestamp="00:01", text="a", user_id=1)
    note2 = Note(video_id=video.video_id, timestamp="00:02", text="b", user_id=1)
    db_session.add_all([note1, note2])
    db_session.commit()

    notes = notes_service.list_notes_for_video(db_session, 1, video.video_id)
    assert [note.id for note in notes] == [note1.id, note2.id]


def test_push_note_to_sqs_sends_payload(monkeypatch):
    monkeypatch.setattr(
        notes_service.settings,
        "sqs_ai_note_queue_url",
        "https://sqs.test/queue",
        raising=False,
    )
    monkeypatch.setattr(
        notes_service.settings, "aws_access_key_id", "key", raising=False
    )
    monkeypatch.setattr(
        notes_service.settings, "aws_secret_access_key", "secret", raising=False
    )
    monkeypatch.setattr(
        notes_service.settings, "aws_region", "ap-south-1", raising=False
    )

    captured = {}

    class _FakeSQS:
        def send_message(self, QueueUrl, MessageBody):
            captured["QueueUrl"] = QueueUrl
            captured["MessageBody"] = MessageBody

    def _fake_client(name, **kwargs):
        captured["ClientName"] = name
        captured["ClientKwargs"] = kwargs
        return _FakeSQS()

    monkeypatch.setattr(notes_service.boto3, "client", _fake_client)

    note = Note(id=42, video_id="abc123DEF45", timestamp="00:01", user_id=7)
    notes_service.push_note_to_sqs(note)

    assert captured["ClientName"] == "sqs"
    assert captured["ClientKwargs"]["region_name"] == "ap-south-1"
    assert captured["ClientKwargs"]["aws_access_key_id"] == "key"
    assert captured["ClientKwargs"]["aws_secret_access_key"] == "secret"
    assert captured["QueueUrl"] == "https://sqs.test/queue"
    assert '"id": 42' in captured["MessageBody"]
