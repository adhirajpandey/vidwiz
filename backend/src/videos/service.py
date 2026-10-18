import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.videos.models import Video
from src import transcripts
from src.internal import constants as internal_constants
from src.internal.models import Task, TaskStatus
from src.videos.schemas import (
    TranscriptRead,
    TranscriptSegment,
    VideoRead,
    VideoStreamPayload,
)

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


def get_transcript(db: Session, video: Video) -> TranscriptRead:
    if video.transcript_available:
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
            video_id=video.video_id, status="ready", segments=segments
        )
    return TranscriptRead(
        video_id=video.video_id,
        status="unavailable"
        if _transcript_failed(db, video.video_id)
        else "processing",
        segments=[],
    )


def _transcript_failed(db: Session, video_id: str) -> bool:
    """True when the latest transcript task for the video failed for good."""
    tasks = (
        db.execute(
            select(Task)
            .where(Task.task_type == internal_constants.FETCH_TRANSCRIPT_TASK_TYPE)
            .order_by(Task.id.desc())
        )
        .scalars()
        .all()
    )
    for task in tasks:
        if (task.task_details or {}).get("video_id") == video_id:
            return (
                task.status == TaskStatus.FAILED
                and task.retry_count >= internal_constants.TASK_MAX_RETRIES
            )
    return False


def is_video_ready(video: Video) -> bool:
    return (
        video.video_metadata is not None
        and video.transcript_available
        and video.summary is not None
    )


async def stream_video_events(video_id: str) -> AsyncGenerator[str, None]:
    logger.debug("Streaming video events", extra={"video_id": video_id})
    video = await _fetch_video(video_id)
    if not video:
        logger.debug("Video not found for stream", extra={"video_id": video_id})
        return

    last_state = _video_state(video)
    yield _format_event("snapshot", video)

    if is_video_ready(video):
        logger.debug("Video already ready", extra={"video_id": video_id})
        yield _format_event("done", video)
        return

    timeout_seconds = 60
    poll_interval = 2
    deadline = asyncio.get_running_loop().time() + timeout_seconds

    while asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(poll_interval)
        video = await _fetch_video(video_id)
        if not video:
            logger.debug("Video missing during stream", extra={"video_id": video_id})
            return

        current_state = _video_state(video)
        if current_state != last_state:
            last_state = current_state
            yield _format_event("update", video)

        if is_video_ready(video):
            logger.debug("Video ready during stream", extra={"video_id": video_id})
            yield _format_event("done", video)
            return


def _video_state(video: Video) -> tuple[bool, bool, bool]:
    return (
        video.video_metadata is not None,
        video.transcript_available,
        video.summary is not None,
    )


def _format_event(event: str, video: Video) -> str:
    payload = VideoStreamPayload(event=event, video=VideoRead.model_validate(video))
    data = json.dumps(payload.model_dump(mode="json"))
    return f"event: {event}\ndata: {data}\n\n"


async def _fetch_video(video_id: str) -> Video | None:
    def _query() -> Video | None:
        db = SessionLocal()
        try:
            return get_video_by_id(db, video_id)
        finally:
            db.close()

    return await run_in_threadpool(_query)
