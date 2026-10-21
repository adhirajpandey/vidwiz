import boto3
import pytest

from src.config import settings
from src.internal import service as internal_service
from src.internal import scheduling as internal_scheduling
from src.internal import constants as internal_constants
from src.internal.models import Task, TaskStatus
from src.videos.models import TranscriptStatus, Video
from src.internal.schemas import TaskResultRequest


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
    )
    assert claimed is not None
    assert claimed.status == TaskStatus.IN_PROGRESS
    assert claimed.retry_count == 1


def test_poll_for_task_ends_transaction_before_waiting(db_session, monkeypatch):
    in_transaction_while_waiting = []

    def fake_sleep(_seconds):
        in_transaction_while_waiting.append(db_session.in_transaction())

    monkeypatch.setattr(internal_service.time, "sleep", fake_sleep)
    claimed = internal_service.poll_for_task(
        db_session,
        internal_constants.FETCH_METADATA_TASK_TYPE,
        timeout=0.05,
        poll_interval=0.01,
    )

    assert claimed is None
    assert in_transaction_while_waiting
    assert not any(in_transaction_while_waiting)


def test_submit_task_result_validates_inputs(db_session):
    task = Task(
        task_type=internal_constants.FETCH_TRANSCRIPT_TASK_TYPE,
        status=TaskStatus.IN_PROGRESS,
        task_details={"video_id": "abc123DEF45"},
        retry_count=0,
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
        )


def test_submit_transcript_result_failure_paths(db_session):
    task = Task(
        task_type=internal_constants.FETCH_TRANSCRIPT_TASK_TYPE,
        status=TaskStatus.IN_PROGRESS,
        task_details={"video_id": "abc123DEF45"},
        retry_count=internal_constants.TASK_MAX_RETRIES,
    )
    db_session.add(task)
    db_session.commit()

    result = internal_service.submit_task_result(
        db_session,
        task.id,
        TaskResultRequest(
            video_id="abc123DEF45",
            success=False,
            transcript=None,
            metadata=None,
            error_message="boom",
        ),
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
    )
    db_session.add_all([video, task])
    db_session.commit()

    result = internal_service.submit_task_result(
        db_session,
        task.id,
        TaskResultRequest(
            video_id="abc123DEF45",
            success=True,
            transcript=None,
            metadata={"title": "Video"},
            error_message=None,
        ),
    )
    assert result.status == TaskStatus.COMPLETED
    updated = db_session.get(Video, video.id)
    assert updated.video_metadata == {"title": "Video"}
    assert updated.title == "Video"


def test_store_transcript_in_s3_no_config(monkeypatch):
    monkeypatch.setattr(
        settings,
        "s3_transcript_bucket_name",
        None,
        raising=False,
    )
    internal_service.store_transcript_in_s3("abc123DEF45", [{"text": "hi"}])


def test_store_transcript_in_s3_success(monkeypatch):
    monkeypatch.setattr(
        settings,
        "s3_transcript_bucket_name",
        "bucket",
        raising=False,
    )
    monkeypatch.setattr(
        settings,
        "aws_access_key_id",
        "key",
        raising=False,
    )
    monkeypatch.setattr(
        settings,
        "aws_secret_access_key",
        "secret",
        raising=False,
    )
    monkeypatch.setattr(
        settings,
        "aws_region",
        "us-east-1",
        raising=False,
    )

    captured = {}

    class _S3:
        def put_object(self, Bucket, Key, Body, ContentType):
            captured["Bucket"] = Bucket
            captured["Key"] = Key

    monkeypatch.setattr(boto3, "client", lambda *args, **kwargs: _S3())
    internal_service.store_transcript_in_s3("abc123DEF45", [{"text": "hi"}])
    assert captured["Bucket"] == "bucket"
    assert captured["Key"] == "transcripts/abc123DEF45.json"


def test_store_summary_merges_miscellaneous_data(db_session):
    video = Video(
        video_id="summary12345",
        title="Video",
        miscellaneous_data={
            "existing_key": "preserved",
            "nested": {"preserved": True, "replaced": "old"},
        },
    )
    db_session.add(video)
    db_session.commit()

    result = internal_service.store_summary(
        db_session,
        video.video_id,
        "Generated summary",
        {
            "nested": {"replaced": "new"},
            "suggested_questions": [
                "What is the first idea?",
                "How is the idea supported?",
                "What conclusion is reached?",
            ],
        },
    )

    assert result.summary == "Generated summary"
    assert result.miscellaneous_data == {
        "existing_key": "preserved",
        "nested": {"replaced": "new"},
        "suggested_questions": [
            "What is the first idea?",
            "How is the idea supported?",
            "What conclusion is reached?",
        ],
    }


def test_create_task_idempotent(db_session):
    first = internal_scheduling.create_task_idempotent(
        db_session, internal_constants.FETCH_TRANSCRIPT_TASK_TYPE, "abc123DEF45"
    )
    second = internal_scheduling.create_task_idempotent(
        db_session, internal_constants.FETCH_TRANSCRIPT_TASK_TYPE, "abc123DEF45"
    )
    assert first.id == second.id


def test_prepare_video_schedules_missing_tasks(db_session):
    existing = Video(video_id="vidschedule2", transcript_status=TranscriptStatus.READY)
    db_session.add(existing)
    db_session.commit()

    created = internal_scheduling.prepare_video(db_session, "vidschedule1")
    prepared = internal_scheduling.prepare_video(db_session, "vidschedule2")

    assert created.video_id == "vidschedule1"
    assert prepared.id == existing.id
    tasks = {
        (task.task_type, task.task_details["video_id"])
        for task in db_session.query(Task).all()
    }
    assert tasks == {
        (internal_constants.FETCH_METADATA_TASK_TYPE, "vidschedule1"),
        (internal_constants.FETCH_TRANSCRIPT_TASK_TYPE, "vidschedule1"),
        (internal_constants.FETCH_METADATA_TASK_TYPE, "vidschedule2"),
    }


@pytest.fixture
def overview_jobs(monkeypatch):
    from src.videos import overview

    sent = []
    monkeypatch.setattr(
        overview, "send_job", lambda _url, payload: sent.append(payload)
    )
    return sent


def _claimed_transcript_task(db_session, video_id: str, retry_count: int = 1) -> Task:
    task = Task(
        task_type=internal_constants.FETCH_TRANSCRIPT_TASK_TYPE,
        status=TaskStatus.IN_PROGRESS,
        task_details={"video_id": video_id},
        retry_count=retry_count,
    )
    db_session.add(task)
    db_session.commit()
    return task


def test_transcript_task_success_queues_the_overview(
    db_session, monkeypatch, overview_jobs
):
    from src.videos.models import OverviewStatus

    monkeypatch.setattr(internal_service, "store_transcript_in_s3", lambda *_a: None)
    video = Video(video_id="trsucc12345")
    db_session.add(video)
    task = _claimed_transcript_task(db_session, video.video_id)

    internal_service.submit_task_result(
        db_session,
        task.id,
        TaskResultRequest(
            video_id=video.video_id,
            success=True,
            transcript=[{"text": "hi", "offset": 0, "duration": 1}],
        ),
    )

    db_session.refresh(video)
    assert video.transcript_status == TranscriptStatus.READY
    assert video.overview_status == OverviewStatus.QUEUED
    assert overview_jobs == [{"video_id": "trsucc12345"}]


@pytest.mark.parametrize("final_failure", [True, False])
def test_transcript_task_without_a_transcript_marks_it_unavailable(
    db_session, overview_jobs, final_failure
):
    from src.videos.models import OverviewStatus

    video = Video(video_id="trnone12345")
    db_session.add(video)
    task = _claimed_transcript_task(
        db_session, video.video_id, retry_count=internal_constants.TASK_MAX_RETRIES
    )
    result = (
        TaskResultRequest(video_id=video.video_id, success=False, error_message="none")
        if final_failure
        else TaskResultRequest(video_id=video.video_id, success=True, transcript=None)
    )

    internal_service.submit_task_result(db_session, task.id, result)

    db_session.refresh(video)
    assert video.transcript_status == TranscriptStatus.UNAVAILABLE
    assert video.overview_status == OverviewStatus.NO_TRANSCRIPT
    assert overview_jobs == []


def test_saving_a_summary_marks_the_overview_ready(db_session):
    from src.videos.models import OverviewStatus

    video = Video(video_id="sumready123", overview_status=OverviewStatus.QUEUED)
    db_session.add(video)
    db_session.commit()

    internal_service.store_summary(db_session, video.video_id, "Summary")

    assert video.overview_status == OverviewStatus.READY


def test_fail_overview_only_fails_a_queued_overview(db_session):
    from src.exceptions import NotFoundError
    from src.videos.models import OverviewStatus

    queued = Video(video_id="failq123456", overview_status=OverviewStatus.QUEUED)
    ready = Video(video_id="failr123456", overview_status=OverviewStatus.READY)
    db_session.add_all([queued, ready])
    db_session.commit()

    assert (
        internal_service.fail_overview(db_session, queued.video_id).overview_status
        == OverviewStatus.FAILED
    )
    assert (
        internal_service.fail_overview(db_session, ready.video_id).overview_status
        == OverviewStatus.READY
    )
    with pytest.raises(NotFoundError):
        internal_service.fail_overview(db_session, "missing1234")


def test_new_capture_retries_an_unavailable_transcript(db_session):
    from src.videos.models import OverviewStatus

    video = Video(
        video_id="retrytr1234",
        transcript_status=TranscriptStatus.UNAVAILABLE,
        overview_status=OverviewStatus.NO_TRANSCRIPT,
    )
    db_session.add(video)
    db_session.commit()

    internal_scheduling.schedule_video_tasks(db_session, video)

    assert video.transcript_status == TranscriptStatus.PENDING
    assert video.overview_status == OverviewStatus.PENDING
