import asyncio
import json
import math
from typing import AsyncGenerator, Iterable

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.notes.models import Note
from src.videos.models import Video
from src.videos.schemas import (
    VideoListParams,
    VideoListResponse,
    VideoRead,
    VideoSearchItem,
    VideoStreamPayload,
)


SORT_MAPPING = {
    "created_at_desc": desc(Video.created_at),
    "created_at_asc": asc(Video.created_at),
    "title_asc": asc(Video.title),
    "title_desc": desc(Video.title),
}


def get_video_by_id(db: Session, video_id: str) -> Video | None:
    return db.execute(
        select(Video).where(Video.video_id == video_id)
    ).scalar_one_or_none()


def get_video_for_user(db: Session, user_id: int, video_id: str) -> Video | None:
    query = select(Video).where(
        Video.video_id == video_id,
        Video.notes.any(Note.user_id == user_id),
    )
    return db.execute(query).scalar_one_or_none()


def list_videos_for_user(
    db: Session, user_id: int, params: VideoListParams
) -> VideoListResponse:
    base_query = (
        select(Video.id)
        .join(Note, Video.video_id == Note.video_id)
        .where(Note.user_id == user_id)
    )

    if params.q:
        base_query = base_query.where(Video.title.ilike(f"%{params.q}%"))

    distinct_ids = base_query.distinct().subquery()
    total = db.execute(select(func.count()).select_from(distinct_ids)).scalar_one()

    order_by = SORT_MAPPING[params.sort]
    videos = (
        db.execute(
            select(Video)
            .join(distinct_ids, Video.id == distinct_ids.c.id)
            .order_by(order_by)
            .offset((params.page - 1) * params.per_page)
            .limit(params.per_page)
        )
        .scalars()
        .all()
    )

    return VideoListResponse(
        videos=_serialize_videos(videos),
        total=total,
        page=params.page,
        per_page=params.per_page,
        total_pages=_compute_total_pages(total, params.per_page),
    )


def _serialize_videos(videos: Iterable[Video]) -> list[VideoSearchItem]:
    return [
        VideoSearchItem(
            video_id=video.video_id,
            title=video.title,
            metadata=video.video_metadata,
        )
        for video in videos
    ]


def _compute_total_pages(total: int, per_page: int) -> int:
    if total == 0:
        return 0
    return math.ceil(total / per_page)


def is_video_ready(video: Video) -> bool:
    return (
        video.video_metadata is not None
        and video.transcript_available
        and video.summary is not None
    )


async def stream_video_events(video_id: str) -> AsyncGenerator[str, None]:
    video = await _fetch_video(video_id)
    if not video:
        return

    last_state = _video_state(video)
    yield _format_event("snapshot", video)

    if is_video_ready(video):
        yield _format_event("done", video)
        return

    timeout_seconds = 60
    poll_interval = 2
    deadline = asyncio.get_running_loop().time() + timeout_seconds

    while asyncio.get_running_loop().time() < deadline:
        await asyncio.sleep(poll_interval)
        video = await _fetch_video(video_id)
        if not video:
            return

        current_state = _video_state(video)
        if current_state != last_state:
            last_state = current_state
            yield _format_event("update", video)

        if is_video_ready(video):
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
