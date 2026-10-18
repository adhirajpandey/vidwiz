"""Markdown export of moments, with timestamped YouTube links."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.library.models import LibraryItem
from src.moments.models import Moment
from src.videos.models import Video


def _clock(seconds: int) -> str:
    hours, rest = divmod(max(seconds, 0), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def _link(video_id: str, seconds: int) -> str:
    return f"https://youtu.be/{video_id}?t={max(seconds, 0)}"


def _video_section(video: Video, moments: list[Moment], level: int) -> list[str]:
    title = video.title or video.video_id
    lines = [f"{'#' * level} [{title}](https://youtu.be/{video.video_id})", ""]
    for moment in moments:
        start = moment.quote_start_seconds or moment.at_seconds
        lines.append(f"- [{_clock(start)}]({_link(video.video_id, start)})")
        if moment.note:
            lines.append(f"  - {moment.note.replace(chr(10), ' ')}")
        if moment.ai_text:
            lines.append(f"  - AI: {moment.ai_text}")
        if moment.quote:
            lines.append(f"  > {moment.quote}")
    lines.append("")
    return lines


def _moments(db: Session, user_id: int, video_id: str | None = None) -> list[Moment]:
    query = (
        select(Moment)
        .where(Moment.user_id == user_id, Moment.video_id.is_not(None))
        .order_by(Moment.video_id, Moment.at_seconds, Moment.id)
    )
    if video_id:
        query = query.where(Moment.video_id == video_id)
    return db.execute(query).scalars().all()


def video_markdown(db: Session, user_id: int, video: Video) -> str:
    moments = _moments(db, user_id, video.video_id)
    lines = _video_section(video, moments, level=1)
    if not moments:
        lines.append("No moments yet.")
    return "\n".join(lines).rstrip() + "\n"


def library_markdown(db: Session, user_id: int) -> str:
    videos = (
        db.execute(
            select(Video)
            .join(LibraryItem, LibraryItem.video_id == Video.video_id)
            .where(LibraryItem.user_id == user_id)
            .order_by(LibraryItem.added_at.desc(), Video.id.desc())
        )
        .scalars()
        .all()
    )
    by_video: dict[str, list[Moment]] = {}
    for moment in _moments(db, user_id):
        by_video.setdefault(moment.video_id, []).append(moment)
    lines = ["# VidWiz library", ""]
    for video in videos:
        if by_video.get(video.video_id):
            lines += _video_section(video, by_video[video.video_id], level=2)
    return "\n".join(lines).rstrip() + "\n"
