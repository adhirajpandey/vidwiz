import pytest

from src.auth.models import User
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


def test_create_note_triggers_ai_when_enabled_and_ready(db_session, monkeypatch):
    user = User(
        email="ai@example.com",
        name="AI User",
        profile_data={"ai_notes_enabled": True},
    )
    video = Video(video_id="ai123456789", title="AI Video", transcript_available=True)
    db_session.add_all([user, video])
    db_session.commit()

    called = {"count": 0}

    def _fake_push(note):
        called["count"] += 1

    monkeypatch.setattr(notes_service, "push_note_to_sqs", _fake_push)

    note = notes_service.create_note_for_user(
        db_session, video.video_id, "00:01", None, user.id
    )
    assert note.id is not None
    assert called["count"] == 1


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


def test_create_note_does_not_trigger_ai_when_transcript_missing(db_session, monkeypatch):
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


def test_update_note_triggers_ai_when_generated_by_ai_true(db_session, monkeypatch):
    video = Video(video_id="ai523456789", title="AI Video", transcript_available=True)
    note = Note(video_id=video.video_id, timestamp="00:01", text=None, user_id=1)
    db_session.add_all([video, note])
    db_session.commit()
    db_session.refresh(note)

    called = {"count": 0}

    def _fake_push(_note):
        called["count"] += 1

    monkeypatch.setattr(notes_service, "push_note_to_sqs", _fake_push)

    notes_service.update_note(db_session, note, text=None, generated_by_ai=True)
    assert called["count"] == 1


def test_update_note_does_not_trigger_ai_when_generated_by_ai_false(db_session, monkeypatch):
    video = Video(video_id="ai623456789", title="AI Video", transcript_available=True)
    note = Note(video_id=video.video_id, timestamp="00:01", text=None, user_id=1)
    db_session.add_all([video, note])
    db_session.commit()
    db_session.refresh(note)

    monkeypatch.setattr(notes_service, "push_note_to_sqs", lambda note: pytest.fail())

    notes_service.update_note(db_session, note, text="updated", generated_by_ai=False)


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
    monkeypatch.setattr(notes_service.settings, "sqs_ai_note_queue_url", None, raising=False)
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

    captured = {}

    class _FakeSQS:
        def send_message(self, QueueUrl, MessageBody):
            captured["QueueUrl"] = QueueUrl
            captured["MessageBody"] = MessageBody

    monkeypatch.setattr(notes_service.boto3, "client", lambda name: _FakeSQS())

    note = Note(id=42, video_id="abc123DEF45", timestamp="00:01", user_id=7)
    notes_service.push_note_to_sqs(note)

    assert captured["QueueUrl"] == "https://sqs.test/queue"
    assert "\"id\": 42" in captured["MessageBody"]
