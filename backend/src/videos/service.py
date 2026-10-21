import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from src import transcripts
from src.videos import overview
from src.videos.models import TranscriptStatus, Video
from src.videos.schemas import TranscriptRead, TranscriptSegment

logger = logging.getLogger(__name__)


def get_video_by_id(db: Session, video_id: str) -> Video | None:
    logger.debug("Fetching video by id", extra={"video_id": video_id})
    return db.execute(
        select(Video).where(Video.video_id == video_id)
    ).scalar_one_or_none()


def get_or_create_video(db: Session, video_id: str, title: str | None = None) -> Video:
    logger.debug(
        "Get or create video",
        extra={"video_id": video_id, "title_provided": title is not None},
    )
    video = get_video_by_id(db, video_id)
    if video is None:
        video = Video(video_id=video_id, title=title)
        db.add(video)
        logger.debug("Creating video", extra={"video_id": video_id})
    elif title and not video.title:
        video.title = title
        logger.debug("Updating video title", extra={"video_id": video_id})
    else:
        return video
    db.commit()
    db.refresh(video)
    return video


def mark_transcript_ready(db: Session, video: Video) -> None:
    """Record the stored transcript, commit, and queue the overview."""
    video.transcript_status = TranscriptStatus.READY
    db.commit()
    overview.on_transcript_ready(db, video)


def mark_transcript_unavailable(video: Video) -> None:
    video.transcript_status = TranscriptStatus.UNAVAILABLE
    overview.on_transcript_unavailable(video)


def mark_transcript_pending(video: Video) -> None:
    video.transcript_status = TranscriptStatus.PENDING
    overview.on_transcript_pending(video)


def get_transcript(video: Video) -> TranscriptRead:
    if not video.has_transcript:
        return TranscriptRead(
            video_id=video.video_id, status=video.transcript_status, segments=[]
        )
    stored = transcripts.load_transcript(video.video_id) or []
    segments = []
    for item in stored:
        if not isinstance(item, dict):
            continue
        times = transcripts.segment_times(item)
        text = " ".join(str(item.get("text") or "").split())
        if times and text:
            segments.append(
                TranscriptSegment(
                    start_seconds=times[0], end_seconds=times[1], text=text
                )
            )
    segments.sort(key=lambda segment: segment.start_seconds)
    return TranscriptRead(
        video_id=video.video_id, status=TranscriptStatus.READY, segments=segments
    )
