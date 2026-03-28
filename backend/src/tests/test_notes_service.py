import pytest

from src.auth.models import User
from src.exceptions import ForbiddenError, InternalServerError, NotFoundError
from src.notes import service as notes_service
from src.notes.models import Note
from src.videos.models import Video


def test_get_or_create_video_creates_and_updates_title(db_session):
    video, created = notes_service.get_or_create_video(
        db_session, "vid12345678", "Title"
    )
    assert created is True
    assert video.title == "Title"

    video_again, created = notes_service.get_or_create_video(
        db_session, "vid12345678", "New Title"
    )
    assert created is False
    assert video_again.id == video.id
    assert video_again.title == "Title"

    video_blank, created = notes_service.get_or_create_video(
        db_session, "vid00000000", None
    )
    assert created is True
    assert video_blank.title is None

    video_updated, created = notes_service.get_or_create_video(
        db_session, "vid00000000", "Filled"
    )
    assert created is False
    assert video_updated.title == "Filled"


def test_get_or_create_video_schedules_tasks_on_create(db_session, monkeypatch):
    scheduled = []

    def fake_schedule(db, video):
        scheduled.append(video.video_id)

    monkeypatch.setattr(notes_service, "schedule_video_tasks", fake_schedule)

    video, created = notes_service.get_or_create_video(db_session, "vidschedule1", None)
    assert created is True
    assert video.video_id == "vidschedule1"
    assert scheduled == ["vidschedule1"]


def test_get_or_create_video_schedules_tasks_on_existing(db_session, monkeypatch):
    video = Video(video_id="vidschedule2", title=None, transcript_available=False)
    db_session.add(video)
    db_session.commit()

    scheduled = []

    def fake_schedule(db, scheduled_video):
        scheduled.append(scheduled_video.video_id)

    monkeypatch.setattr(notes_service, "schedule_video_tasks", fake_schedule)

    video_out, created = notes_service.get_or_create_video(
        db_session, "vidschedule2", None
    )
    assert created is False
    assert video_out.id == video.id
    assert scheduled == ["vidschedule2"]


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

    monkeypatch.setattr(notes_service, "schedule_video_tasks", fake_schedule)
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


def test_resolve_video_by_title_returns_top_result(monkeypatch):
    captured = {}

    class FakeRequest:
        def execute(self):
            return {
                "items": [
                    {
                        "id": {"videoId": "resolved12345"},
                        "snippet": {"title": "Resolved Title"},
                    }
                ]
            }

    class FakeSearch:
        def list(self, **kwargs):
            captured["kwargs"] = kwargs
            return FakeRequest()

    class FakeYoutube:
        def search(self):
            return FakeSearch()

    monkeypatch.setattr(notes_service, "_build_youtube_client", lambda: FakeYoutube())

    video_id, title = notes_service.resolve_video_by_title("Search Title")

    assert video_id == "resolved12345"
    assert title == "Resolved Title"
    assert captured["kwargs"] == {
        "q": "Search Title",
        "part": "snippet",
        "type": "video",
        "maxResults": 1,
    }


def test_resolve_video_by_title_decodes_html_entities(monkeypatch):
    class FakeRequest:
        def execute(self):
            return {
                "items": [
                    {
                        "id": {"videoId": "resolved12345"},
                        "snippet": {"title": "The Privacy Iceberg (I&#39;m deep)"},
                    }
                ]
            }

    class FakeSearch:
        def list(self, **kwargs):
            return FakeRequest()

    class FakeYoutube:
        def search(self):
            return FakeSearch()

    monkeypatch.setattr(notes_service, "_build_youtube_client", lambda: FakeYoutube())

    video_id, title = notes_service.resolve_video_by_title("Privacy Iceberg")

    assert video_id == "resolved12345"
    assert title == "The Privacy Iceberg (I'm deep)"


def test_resolve_video_by_title_raises_not_found_for_empty_results(monkeypatch):
    class FakeRequest:
        def execute(self):
            return {"items": []}

    class FakeSearch:
        def list(self, **kwargs):
            return FakeRequest()

    class FakeYoutube:
        def search(self):
            return FakeSearch()

    monkeypatch.setattr(notes_service, "_build_youtube_client", lambda: FakeYoutube())

    with pytest.raises(NotFoundError):
        notes_service.resolve_video_by_title("Missing Video")


def test_resolve_video_by_title_raises_internal_error_for_search_failures(monkeypatch):
    class FakeRequest:
        def execute(self):
            raise RuntimeError("boom")

    class FakeSearch:
        def list(self, **kwargs):
            return FakeRequest()

    class FakeYoutube:
        def search(self):
            return FakeSearch()

    monkeypatch.setattr(notes_service, "_build_youtube_client", lambda: FakeYoutube())

    with pytest.raises(InternalServerError):
        notes_service.resolve_video_by_title("Exploding Search")


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


def test_push_note_to_sqs_no_queue_url(monkeypatch):
    monkeypatch.setattr(
        notes_service.settings, "sqs_ai_note_queue_url", None, raising=False
    )
    notes_service.push_note_to_sqs(
        Note(id=1, video_id="abc123DEF45", timestamp="00:01", user_id=1)
    )


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
