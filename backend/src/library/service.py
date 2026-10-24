import logging

from sqlalchemy import case, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.conversations.models import Conversation, Message
from src.library.models import LibraryItem
from src.library.schemas import (
    LatestMoment,
    LibraryCounts,
    LibraryParams,
    LibraryResponse,
    LibraryVideo,
)
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
            func.count(func.distinct(Conversation.id))
            .filter(Message.role == "user")
            .label("chat_count"),
        )
        .join(Message)
        .where(Conversation.user_id == user_id)
        .group_by(Conversation.video_id)
        .subquery()
    )
    latest = (
        select(
            Moment.video_id,
            func.coalesce(Moment.note, Moment.ai_text, Moment.quote).label("text"),
            case(
                (Moment.note.is_not(None), "note"),
                (Moment.ai_text.is_not(None), "ai"),
                else_="quote",
            ).label("kind"),
        )
        .where(Moment.user_id == user_id)
        .distinct(Moment.video_id)
        .order_by(Moment.video_id, Moment.created_at.desc(), Moment.id.desc())
        .subquery()
    )
    moment_count = func.coalesce(moments.c.moment_count, 0)
    chat_count = func.coalesce(chats.c.chat_count, 0)
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
            moment_count,
            chat_count,
            latest.c.text,
            latest.c.kind,
            activity,
        )
        .join(LibraryItem, LibraryItem.video_id == Video.video_id)
        .outerjoin(moments, moments.c.video_id == Video.video_id)
        .outerjoin(chats, chats.c.video_id == Video.video_id)
        .outerjoin(latest, latest.c.video_id == Video.video_id)
        .where(LibraryItem.user_id == user_id)
    )
    if params.q:
        query = query.where(
            or_(
                Video.title.icontains(params.q, autoescape=True),
                Video.video_metadata["uploader"]
                .as_string()
                .icontains(params.q, autoescape=True),
                Video.video_id == params.q,
            )
        )

    # Counts follow the search, before applying the selected view or pagination.
    counts_row = db.execute(
        query.with_only_columns(
            func.count(),
            func.count().filter(moment_count > 0),
            func.count().filter(chat_count > 0),
        )
    ).one()
    counts = LibraryCounts(
        all=counts_row[0], with_moments=counts_row[1], with_chats=counts_row[2]
    )
    if params.view == "with_moments":
        query = query.where(moment_count > 0)
    elif params.view == "with_chats":
        query = query.where(chat_count > 0)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = {
        "activity_desc": activity.desc(),
        "added_desc": LibraryItem.added_at.desc(),
        "title_asc": Video.title.asc().nulls_last(),
        "title_desc": Video.title.desc().nulls_last(),
        "moments_desc": moment_count.desc(),
        "chats_desc": chat_count.desc(),
    }[params.sort]
    rows = db.execute(
        query.order_by(order, activity.desc(), Video.id.desc())
        .offset((params.page - 1) * params.per_page)
        .limit(params.per_page)
    ).all()
    return LibraryResponse(
        videos=[
            LibraryVideo(
                video_id=video.video_id,
                title=video.title,
                metadata=video.video_metadata,
                transcript_status=video.transcript_status,
                overview_status=video.overview_status,
                moment_count=count,
                chat_count=chat_total,
                latest_moment=LatestMoment(text=text, kind=kind) if text else None,
                added_at=added_at,
                last_activity_at=last_activity_at,
            )
            for video, added_at, count, chat_total, text, kind, last_activity_at in rows
        ],
        total=total,
        counts=counts,
        page=params.page,
        per_page=params.per_page,
        total_pages=-(-total // params.per_page),
    )
