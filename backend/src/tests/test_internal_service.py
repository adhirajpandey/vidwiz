import pytest

from src.internal import service as internal_service
from src.internal import scheduling as internal_scheduling
from src.internal import constants as internal_constants
from src.internal.models import Task, TaskStatus
from src.videos.models import Video
from src.notes.models import Note
from src.auth.models import User


def test_poll_for_task_claims_pending(db_session):
    task = Task(
        task_type=internal_constants.FETCH_METADATA_TASK_TYPE,
        status=TaskStatus.PENDING,
        task_details={"video_id": "abc123DEF45"},
        retry_count=0,
    )
    db_session.add(task)
    db_session.commit()

    claimed = internal_service.poll_for_task(
        db_session,
        internal_constants.FETCH_METADATA_TASK_TYPE,
        timeout=1,
        poll_interval=0,
        max_retries=2,
        in_progress_timeout=10,
        worker_user_id=7,
    )
    assert claimed is not None
    assert claimed.status == TaskStatus.IN_PROGRESS
    assert claimed.retry_count == 1
    assert claimed.worker_details["worker_user_id"] == 7


def test_submit_task_result_validates_inputs(db_session):
    task = Task(
        task_type=internal_constants.FETCH_TRANSCRIPT_TASK_TYPE,
        status=TaskStatus.IN_PROGRESS,
        task_details={"video_id": "abc123DEF45"},
        retry_count=0,
        worker_details={"worker_user_id": 1},
    )
    db_session.add(task)
    db_session.commit()

    with pytest.raises(Exception):
        internal_service.submit_task_result(
            db_session,
            task.id,
            "other1234567",
            True,
            transcript=[{"text": "hi"}],
            metadata=None,
            error_message=None,
            worker_user_id=1,
        )

    with pytest.raises(Exception):
        internal_service.submit_task_result(
            db_session,
            task.id,
            "abc123DEF45",
            True,
            transcript=None,
            metadata={"title": "bad"},
            error_message=None,
            worker_user_id=1,
        )

    with pytest.raises(Exception):
        internal_service.submit_task_result(
            db_session,
            task.id,
            "abc123DEF45",
            True,
            transcript=[{"text": "hi"}],
            metadata=None,
            error_message=None,
            worker_user_id=999,
        )


def test_submit_transcript_result_failure_paths(db_session):
    task = Task(
        task_type=internal_constants.FETCH_TRANSCRIPT_TASK_TYPE,
        status=TaskStatus.IN_PROGRESS,
        task_details={"video_id": "abc123DEF45"},
        retry_count=internal_constants.FETCH_TRANSCRIPT_MAX_RETRIES,
        worker_details={"worker_user_id": 1},
    )
    db_session.add(task)
    db_session.commit()

    result = internal_service.submit_task_result(
        db_session,
        task.id,
        "abc123DEF45",
        False,
        transcript=None,
        metadata=None,
        error_message="boom",
        worker_user_id=1,
    )
    assert result.status == TaskStatus.FAILED
    assert result.worker_details["error_message"] == "boom"


def test_submit_metadata_result_success(db_session):
    video = Video(video_id="abc123DEF45", title=None)
    task = Task(
        task_type=internal_constants.FETCH_METADATA_TASK_TYPE,
        status=TaskStatus.IN_PROGRESS,
        task_details={"video_id": "abc123DEF45"},
        retry_count=0,
        worker_details={"worker_user_id": 1},
    )
    db_session.add_all([video, task])
    db_session.commit()

    result = internal_service.submit_task_result(
        db_session,
        task.id,
        "abc123DEF45",
        True,
        transcript=None,
        metadata={"title": "Video"},
        error_message=None,
        worker_user_id=1,
    )
    assert result.status == TaskStatus.COMPLETED
    updated = db_session.get(Video, video.id)
    assert updated.video_metadata == {"title": "Video"}


def test_store_transcript_in_s3_no_config(monkeypatch):
    monkeypatch.setattr(
        internal_service.conversations_settings, "s3_bucket_name", None, raising=False
    )
    internal_service.store_transcript_in_s3("abc123DEF45", [{"text": "hi"}])


def test_store_transcript_in_s3_success(monkeypatch):
    monkeypatch.setattr(
        internal_service.conversations_settings,
        "s3_bucket_name",
        "bucket",
        raising=False,
    )
    monkeypatch.setattr(
        internal_service.conversations_settings,
        "aws_access_key_id",
        "key",
        raising=False,
    )
    monkeypatch.setattr(
        internal_service.conversations_settings,
        "aws_secret_access_key",
        "secret",
        raising=False,
    )
    monkeypatch.setattr(
        internal_service.conversations_settings,
        "aws_region",
        "us-east-1",
        raising=False,
    )

    captured = {}

    class _S3:
        def put_object(self, Bucket, Key, Body, ContentType):
            captured["Bucket"] = Bucket
            captured["Key"] = Key

    monkeypatch.setattr(internal_service.boto3, "client", lambda *args, **kwargs: _S3())
    internal_service.store_transcript_in_s3("abc123DEF45", [{"text": "hi"}])
    assert captured["Bucket"] == "bucket"
    assert captured["Key"] == "transcripts/abc123DEF45.json"


def test_fetch_ai_note_task_notes_sqlite_branch(db_session):
    video = Video(video_id="abc123DEF45", title="Video")
    user = User(email="ai@example.com", profile_data={"ai_notes_enabled": True})
    db_session.add_all([video, user])
    db_session.commit()

    note = Note(video_id=video.video_id, timestamp="00:01", text=None, user_id=user.id)
    db_session.add(note)
    db_session.commit()

    video_out, notes = internal_service.fetch_ai_note_task_notes(
        db_session, video.video_id
    )
    assert video_out.video_id == video.video_id
    assert len(notes) == 1


def test_create_task_idempotent(db_session):
    first = internal_scheduling.create_task_idempotent(
        db_session, internal_constants.FETCH_TRANSCRIPT_TASK_TYPE, "abc123DEF45"
    )
    second = internal_scheduling.create_task_idempotent(
        db_session, internal_constants.FETCH_TRANSCRIPT_TASK_TYPE, "abc123DEF45"
    )
    assert first.id == second.id
