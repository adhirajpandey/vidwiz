import asyncio
import json
import math
import logging
from typing import AsyncGenerator

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import asc, desc, func, select, case
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.notes.models import Note
from src.conversations.models import Conversation, Message
from src.videos.models import Video
from src.videos.schemas import (
    LibrarySummary,
    VideoListParams,
    VideoListResponse,
    VideoRead,
    VideoSearchItem,
    VideoStreamPayload,
)

logger = logging.getLogger(__name__)

SORT_MAPPING = {
    "created_at_desc": desc(Video.created_at),
    "created_at_asc": asc(Video.created_at),
    "title_asc": asc(Video.title),
    "title_desc": desc(Video.title),
}


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


def _library_query(user_id: int):
    notes = (
        select(
            Note.video_id,
            func.count(Note.id).label("note_count"),
            func.max(
                case(
                    (Note.updated_at > Note.created_at, Note.updated_at),
                    else_=Note.created_at,
                )
            ).label("note_activity"),
        )
        .where(Note.user_id == user_id)
        .group_by(Note.video_id)
        .subquery()
    )
    chats = (
        select(
            Conversation.video_id,
            func.max(Message.created_at).label("chat_activity"),
        )
        .join(Message)
        .where(Conversation.user_id == user_id)
        .group_by(Conversation.video_id)
        .subquery()
    )
    activity = case(
        (chats.c.chat_activity > notes.c.note_activity, chats.c.chat_activity),
        else_=notes.c.note_activity,
    ).label("last_activity_at")
    return select(Video, notes.c.note_count, activity).join(
        notes, Video.video_id == notes.c.video_id
    ).outerjoin(chats, Video.video_id == chats.c.video_id), activity


def list_videos_for_user(
    db: Session, user_id: int, params: VideoListParams
) -> VideoListResponse:
    query, activity = _library_query(user_id)
    if params.q:
        query = query.where(Video.title.icontains(params.q, autoescape=True))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = (
        activity.desc() if params.sort == "activity_desc" else SORT_MAPPING[params.sort]
    )
    rows = db.execute(
        query.order_by(order, Video.id.asc())
        .offset((params.page - 1) * params.per_page)
        .limit(params.per_page)
    ).all()
    return VideoListResponse(
        videos=[
            VideoSearchItem(
                video_id=v.video_id,
                title=v.title,
                metadata=v.video_metadata,
                note_count=count,
                last_activity_at=active,
            )
            for v, count, active in rows
        ],
        total=total,
        page=params.page,
        per_page=params.per_page,
        total_pages=_compute_total_pages(total, params.per_page),
    )


def get_library_summary(db: Session, user_id: int) -> LibrarySummary:
    library_ids = select(Note.video_id).where(Note.user_id == user_id).distinct()
    notes, ai_notes = db.execute(
        select(
            func.count(Note.id),
            func.coalesce(
                func.sum(case((Note.generated_by_ai.is_(True), 1), else_=0)), 0
            ),
        ).where(Note.user_id == user_id)
    ).one()
    chats = (
        db.scalar(
            select(func.count(Conversation.id)).where(
                Conversation.user_id == user_id,
                Conversation.video_id.in_(library_ids),
                Conversation.messages.any(Message.role == "user"),
            )
        )
        or 0
    )
    recent = list_videos_for_user(
        db, user_id, VideoListParams(per_page=3, sort="activity_desc")
    )
    return LibrarySummary(
        videos=recent.total,
        notes=notes,
        ai_notes=ai_notes,
        wiz_chats=chats,
        recent_videos=recent.videos,
    )


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
