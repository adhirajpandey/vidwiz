from datetime import datetime, timedelta

import pytest
from sqlalchemy import update

from src import transcripts
from src.exceptions import BadRequestError
from src.moments.models import AiStatus, CaptureSource, Moment
from src.videos import overview
from src.videos import service as videos_service
from src.videos.models import OverviewStatus, TranscriptStatus, Video
from src.videos.schemas import VideoRead


@pytest.fixture
def jobs(monkeypatch):
    sent = []
    monkeypatch.setattr(
        overview,
        "send_job",
        lambda queue_url, payload: sent.append((queue_url, payload)),
    )
    return sent


def seed_video(db_session, video_id: str, **fields) -> Video:
    video = Video(video_id=video_id, title=fields.pop("title", None), **fields)
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video


def test_new_videos_start_pending(db_session):
    video = seed_video(db_session, "new12345678")

    assert video.transcript_status == TranscriptStatus.PENDING
    assert video.overview_status == OverviewStatus.PENDING
    assert video.has_transcript is False


def test_video_read_hides_invalid_suggested_questions(db_session):
    video = seed_video(db_session, "invalid1234")
    video.miscellaneous_data = {"suggested_questions": ["Only one?"]}
    db_session.commit()

    read = VideoRead.model_validate(video)

    assert read.suggested_questions is None
    assert read.overview_status == OverviewStatus.PENDING


def test_transcript_ready_queues_the_overview(db_session, jobs):
    video = seed_video(db_session, "ready123456")

    videos_service.mark_transcript_ready(db_session, video)

    assert video.transcript_status == TranscriptStatus.READY
    assert video.overview_status == OverviewStatus.QUEUED
    assert jobs == [("test-summary-queue-url", {"video_id": "ready123456"})]


def test_failed_send_marks_the_overview_failed(db_session, monkeypatch):
    def broken(*_args):
        raise RuntimeError("SQS down")

    monkeypatch.setattr(overview, "send_job", broken)
    video = seed_video(db_session, "broken12345")

    videos_service.mark_transcript_ready(db_session, video)

    assert video.overview_status == OverviewStatus.FAILED


def test_transcript_ready_keeps_an_existing_overview(db_session, jobs):
    video = seed_video(
        db_session, "keep1234567", summary="Done", overview_status=OverviewStatus.READY
    )

    videos_service.mark_transcript_ready(db_session, video)

    assert video.overview_status == OverviewStatus.READY
    assert jobs == []


def test_unavailable_transcript_and_a_new_attempt(db_session, jobs):
    video = seed_video(db_session, "none1234567")

    videos_service.mark_transcript_unavailable(video)
    assert video.transcript_status == TranscriptStatus.UNAVAILABLE
    assert video.overview_status == OverviewStatus.NO_TRANSCRIPT

    videos_service.mark_transcript_pending(video)
    assert video.transcript_status == TranscriptStatus.PENDING
    assert video.overview_status == OverviewStatus.PENDING

    videos_service.mark_transcript_ready(db_session, video)
    assert video.overview_status == OverviewStatus.QUEUED


def test_fail_only_changes_a_queued_overview(db_session):
    video = seed_video(db_session, "fail1234567", overview_status=OverviewStatus.READY)

    overview.fail(video)
    assert video.overview_status == OverviewStatus.READY

    video.overview_status = OverviewStatus.QUEUED
    overview.fail(video)
    assert video.overview_status == OverviewStatus.FAILED


def test_retry_queues_only_failed_overviews_with_a_transcript(db_session, jobs):
    video = seed_video(
        db_session,
        "retry123456",
        transcript_status=TranscriptStatus.READY,
        overview_status=OverviewStatus.READY,
    )
    with pytest.raises(BadRequestError):
        overview.retry(db_session, video)

    video.overview_status = OverviewStatus.FAILED
    overview.retry(db_session, video)
    assert video.overview_status == OverviewStatus.QUEUED
    assert jobs == [("test-summary-queue-url", {"video_id": "retry123456"})]

    no_transcript = seed_video(
        db_session, "notrans1234", overview_status=OverviewStatus.FAILED
    )
    with pytest.raises(BadRequestError):
        overview.retry(db_session, no_transcript)


def test_sweep_fails_only_stale_queued_overviews(db_session):
    stale = seed_video(db_session, "stale123456", overview_status=OverviewStatus.QUEUED)
    fresh = seed_video(db_session, "fresh123456", overview_status=OverviewStatus.QUEUED)
    db_session.execute(
        update(Video)
        .where(Video.id == stale.id)
        .values(overview_status_at=datetime.utcnow() - timedelta(hours=3))
    )
    db_session.commit()

    assert overview.sweep(db_session, timedelta(hours=2)) == 1
    db_session.refresh(stale)
    db_session.refresh(fresh)
    assert stale.overview_status == OverviewStatus.FAILED
    assert fresh.overview_status == OverviewStatus.QUEUED


def test_backfill_candidates_pick_missing_failed_and_legacy(db_session, user):
    ready = TranscriptStatus.READY
    seed_video(db_session, "pending1234", transcript_status=ready)
    seed_video(
        db_session,
        "failed12345",
        transcript_status=ready,
        overview_status=OverviewStatus.FAILED,
    )
    legacy = seed_video(
        db_session,
        "legacy12345",
        transcript_status=ready,
        summary="Old",
        overview_status=OverviewStatus.READY,
    )
    seed_video(
        db_session,
        "current1234",
        transcript_status=ready,
        summary="New",
        overview_status=OverviewStatus.READY,
        miscellaneous_data={
            "key_points": [{"text": "k", "start_seconds": 0, "end_seconds": 1}]
        },
    )
    seed_video(db_session, "notrans1234")
    seed_video(
        db_session,
        "queued12345",
        transcript_status=ready,
        overview_status=OverviewStatus.QUEUED,
    )
    db_session.add(
        Moment(
            user_id=user.id,
            video_id=legacy.video_id,
            at_seconds=1,
            ai_status=AiStatus.NOT_REQUESTED,
            source=CaptureSource.WEB,
        )
    )
    db_session.commit()

    picked = [video.video_id for video in overview.backfill_candidates(db_session, 10)]

    # Recently used videos come first.
    assert picked[0] == "legacy12345"
    assert sorted(picked) == ["failed12345", "legacy12345", "pending1234"]
    assert len(overview.backfill_candidates(db_session, 2)) == 2


def test_get_transcript_reports_the_status(db_session, monkeypatch):
    pending = seed_video(db_session, "trpend12345")
    assert videos_service.get_transcript(pending).status == TranscriptStatus.PENDING

    monkeypatch.setattr(
        transcripts,
        "load_transcript",
        lambda _id: [
            {"text": "second", "offset": 5, "duration": 2},
            {"text": " first ", "offset": 0, "duration": 2},
        ],
    )
    ready = seed_video(
        db_session, "trready1234", transcript_status=TranscriptStatus.READY
    )
    read = videos_service.get_transcript(ready)
    assert read.status == TranscriptStatus.READY
    assert [segment.text for segment in read.segments] == ["first", "second"]


def test_get_or_create_video_creates_and_fills_missing_title(db_session):
    video = videos_service.get_or_create_video(db_session, "vid12345678", "Title")
    assert video.title == "Title"

    again = videos_service.get_or_create_video(db_session, "vid12345678", "New")
    assert again.id == video.id
    assert again.title == "Title"

    blank = videos_service.get_or_create_video(db_session, "vid00000000")
    assert blank.title is None

    filled = videos_service.get_or_create_video(db_session, "vid00000000", "Filled")
    assert filled.id == blank.id
    assert filled.title == "Filled"
