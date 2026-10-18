import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.videos.models import Video
from src.videos.schemas import VideoRead, VideoStreamPayload

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
