import logging

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.conversations.models import Conversation, Message
from src.library.models import LibraryItem
from src.library.schemas import LibraryParams, LibraryResponse, LibraryVideo
from src.moments.models import Moment
from src.videos.models import Video

logger = logging.getLogger(__name__)


def save_video(db: Session, user_id: int, video_id: str) -> None:
    """Add a video to the user's library; saving twice is a no-op."""
    logger.debug("Saving video", extra={"user_id": user_id, "video_id": video_id})
    db.execute(
        insert(LibraryItem)
        .values(user_id=user_id, video_id=video_id)
        .on_conflict_do_nothing(index_elements=["user_id", "video_id"])
    )


def remove_video(db: Session, user_id: int, video_id: str) -> bool:
    item = db.get(LibraryItem, (user_id, video_id))
    if item is None:
        return False
    logger.debug("Removing video", extra={"user_id": user_id, "video_id": video_id})
    db.delete(item)
    db.commit()
    return True


def list_library(db: Session, user_id: int, params: LibraryParams) -> LibraryResponse:
    moments = (
        select(
            Moment.video_id,
            func.count(Moment.id).label("moment_count"),
            func.max(Moment.updated_at).label("moment_activity"),
        )
        .where(Moment.user_id == user_id)
        .group_by(Moment.video_id)
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
    # greatest() ignores nulls in PostgreSQL.
    activity = func.greatest(
        LibraryItem.added_at,
        LibraryItem.last_opened_at,
        moments.c.moment_activity,
        chats.c.chat_activity,
    ).label("last_activity_at")
    query = (
        select(
            Video,
            LibraryItem.added_at,
            func.coalesce(moments.c.moment_count, 0),
            activity,
        )
        .join(LibraryItem, LibraryItem.video_id == Video.video_id)
        .outerjoin(moments, moments.c.video_id == Video.video_id)
        .outerjoin(chats, chats.c.video_id == Video.video_id)
        .where(LibraryItem.user_id == user_id)
    )
    if params.q:
        query = query.where(Video.title.icontains(params.q, autoescape=True))

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = {
        "activity_desc": activity.desc(),
        "added_desc": LibraryItem.added_at.desc(),
        "title_asc": Video.title.asc(),
        "title_desc": Video.title.desc(),
    }[params.sort]
    rows = db.execute(
        query.order_by(order, Video.id.desc())
        .offset((params.page - 1) * params.per_page)
        .limit(params.per_page)
    ).all()
    return LibraryResponse(
        videos=[
            LibraryVideo(
                video_id=video.video_id,
                title=video.title,
                metadata=video.video_metadata,
                transcript_available=bool(video.transcript_available),
                moment_count=count,
                added_at=added_at,
                last_activity_at=last_activity_at,
            )
            for video, added_at, count, last_activity_at in rows
        ],
        total=total,
        page=params.page,
        per_page=params.per_page,
        total_pages=-(-total // params.per_page),
    )
