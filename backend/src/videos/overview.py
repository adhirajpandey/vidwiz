"""Overview state transitions.

pending ──transcript ready──▶ queued ──worker saves──▶ ready
   │                            │  ▲
   │                            │  └──retry / backfill── failed, ready
   │                            └──worker gives up, or sweep──▶ failed
   └──transcript unavailable──▶ no_transcript ──transcript ready──▶ queued

The API is the only place that queues an overview, so every queued job has a
matching state. The worker only generates while the video is queued, which also
makes duplicate SQS deliveries harmless.
"""

import logging
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from src.config import settings
from src.exceptions import BadRequestError
from src.shared.queues import send_job
from src.moments.models import Moment
from src.videos.models import OverviewStatus, TranscriptStatus, Video

logger = logging.getLogger(__name__)

# A new transcript starts an overview from these states.
QUEUE_ON_TRANSCRIPT = {
    OverviewStatus.PENDING,
    OverviewStatus.NO_TRANSCRIPT,
    OverviewStatus.FAILED,
}


def set_status(video: Video, status: OverviewStatus) -> None:
    video.overview_status = status
    video.overview_status_at = func.now()


def queue(db: Session, video: Video) -> None:
    """Mark the overview queued and send the job; a failed send marks it failed."""
    set_status(video, OverviewStatus.QUEUED)
    db.commit()
    try:
        send_job(settings.sqs_ai_summary_queue_url, {"video_id": video.video_id})
        logger.info("Queued overview", extra={"video_id": video.video_id})
    except Exception as exc:
        logger.error(
            "Failed to queue overview",
            extra={"video_id": video.video_id, "error": str(exc)},
        )
        set_status(video, OverviewStatus.FAILED)
        db.commit()
    db.refresh(video)


def on_transcript_ready(db: Session, video: Video) -> None:
    if video.overview_status in QUEUE_ON_TRANSCRIPT:
        queue(db, video)


def on_transcript_unavailable(video: Video) -> None:
    if video.overview_status == OverviewStatus.PENDING:
        set_status(video, OverviewStatus.NO_TRANSCRIPT)


def on_transcript_pending(video: Video) -> None:
    """A new transcript fetch was scheduled after an earlier one failed."""
    if video.overview_status == OverviewStatus.NO_TRANSCRIPT:
        set_status(video, OverviewStatus.PENDING)


def complete(video: Video) -> None:
    set_status(video, OverviewStatus.READY)


def fail(video: Video) -> None:
    # Only a queued overview can fail; a late report after a newer result or a
    # sweep changes nothing.
    if video.overview_status == OverviewStatus.QUEUED:
        set_status(video, OverviewStatus.FAILED)


def retry(db: Session, video: Video) -> None:
    if video.overview_status != OverviewStatus.FAILED:
        raise BadRequestError("Only a failed overview can be retried")
    if not video.has_transcript:
        raise BadRequestError("The video has no transcript")
    queue(db, video)


def sweep(db: Session, older_than: timedelta) -> int:
    """Fail overviews queued longer than any worker attempt can take.

    The worker reports its own failures; this covers jobs whose report never
    arrived, for example when the API was unreachable.
    """
    result = db.execute(
        update(Video)
        .where(
            Video.overview_status == OverviewStatus.QUEUED,
            Video.overview_status_at < func.now() - older_than,
        )
        .values(overview_status=OverviewStatus.FAILED, overview_status_at=func.now())
    )
    db.commit()
    return result.rowcount


def backfill_candidates(db: Session, limit: int) -> list[Video]:
    """Videos with a transcript whose overview is missing, failed, or older
    than key points, most recently used first."""
    last_used = (
        select(Moment.video_id, func.max(Moment.created_at).label("last_used"))
        .where(Moment.video_id.is_not(None))
        .group_by(Moment.video_id)
        .subquery()
    )
    videos = db.execute(
        select(Video)
        .outerjoin(last_used, last_used.c.video_id == Video.video_id)
        .where(
            Video.transcript_status == TranscriptStatus.READY,
            Video.overview_status.in_(
                [OverviewStatus.PENDING, OverviewStatus.FAILED, OverviewStatus.READY]
            ),
        )
        .order_by(last_used.c.last_used.desc().nulls_last(), Video.id.desc())
    ).scalars()
    picked = []
    for video in videos:
        if video.overview_status == OverviewStatus.READY and video.key_points:
            continue
        picked.append(video)
        if len(picked) == limit:
            break
    return picked
