import html
import json
import logging
import boto3
import requests

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from src.auth.models import User
from src.config import settings
from src.exceptions import InternalServerError, NotFoundError
from src.internal.scheduling import prepare_video
from src.notes.models import Note
from src.notes.schemas import NoteSearchItem, NoteSearchResponse
from src.videos.models import Video
from src.videos import service as videos_service
from src.credits import service as credits_service

logger = logging.getLogger(__name__)


def _build_ai_note_queue_payload(note: Note) -> dict[str, int | str]:
    return {
        "id": note.id,
        "video_id": note.video_id,
        "timestamp": note.timestamp,
        "user_id": note.user_id,
    }


YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def resolve_video_by_title(video_title: str) -> tuple[str, str | None]:
    logger.debug("Resolving video by title", extra={"video_title": video_title})
    if not settings.youtube_data_api_key:
        raise InternalServerError("YOUTUBE_DATA_API_KEY is not configured")

    try:
        search = requests.get(
            YOUTUBE_SEARCH_URL,
            params={
                "q": video_title,
                "part": "snippet",
                "type": "video",
                "maxResults": 1,
            },
            # A header keeps the key out of URLs quoted in error messages.
            headers={"X-Goog-Api-Key": settings.youtube_data_api_key},
            timeout=10,
        )
        search.raise_for_status()
        response = search.json()
    except Exception as exc:
        logger.exception("Failed to search YouTube", extra={"video_title": video_title})
        raise InternalServerError("Failed to search YouTube") from exc

    items = response.get("items") or []
    if not items:
        raise NotFoundError("No video found for the provided title")

    item = items[0]
    video_id = (item.get("id") or {}).get("videoId")
    if not video_id:
        raise NotFoundError("No video found for the provided title")

    resolved_title = (item.get("snippet") or {}).get("title")
    if resolved_title is not None:
        resolved_title = html.unescape(resolved_title)
    logger.debug(
        "Resolved video by title",
        extra={"video_title": video_title, "resolved_video_id": video_id},
    )
    return video_id, resolved_title


def push_note_to_sqs(note: Note) -> None:
    ai_note_queue_url = settings.sqs_ai_note_queue_url

    try:
        sqs = boto3.client(
            "sqs",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        payload = _build_ai_note_queue_payload(note)

        sqs.send_message(
            QueueUrl=ai_note_queue_url,
            MessageBody=json.dumps(payload),
        )
        logger.info("Pushed AI note request to SQS", extra={"note_id": note.id})
    except Exception as e:
        logger.error(
            "Failed to push AI note to SQS", extra={"note_id": note.id, "error": str(e)}
        )


def create_note_for_user(
    db: Session, video_id: str, timestamp: str, text: str | None, user_id: int
) -> Note:
    logger.debug(
        "Creating note",
        extra={"user_id": user_id, "video_id": video_id, "has_text": bool(text)},
    )
    note = Note(
        video_id=video_id,
        timestamp=timestamp,
        text=text,
        generated_by_ai=False,
        user_id=user_id,
    )
    db.add(note)
    try:
        db.flush()

        # Check for AI Note Trigger:
        # 1. Text is empty
        trigger_ai = not text

        should_enqueue = False
        if trigger_ai:
            user = db.get(User, user_id)
            if user and user.profile_data and user.profile_data.get("ai_notes_enabled"):
                # Check availability
                video = videos_service.get_video_by_id(db, video_id)
                if video and video.transcript_available:
                    credits_service.charge_ai_note_enqueue(db, user_id, note.id)
                    should_enqueue = True

        db.commit()
        db.refresh(note)
        logger.debug("Created note", extra={"note_id": note.id, "video_id": video_id})
    except Exception:
        db.rollback()
        raise

    if should_enqueue:
        logger.debug(
            "Enqueueing AI note", extra={"note_id": note.id, "user_id": user_id}
        )
        push_note_to_sqs(note)

    return note


def create_note_for_video_title(
    db: Session,
    video_title: str,
    timestamp: str,
    text: str | None,
    user_id: int,
) -> Note:
    resolved_video_id, resolved_title = resolve_video_by_title(video_title)
    prepare_video(db, resolved_video_id, resolved_title)
    return create_note_for_user(db, resolved_video_id, timestamp, text, user_id)


def list_notes_for_video(db: Session, user_id: int, video_id: str) -> list[Note]:
    logger.debug("Listing notes", extra={"user_id": user_id, "video_id": video_id})
    query = (
        select(Note)
        .where(Note.user_id == user_id, Note.video_id == video_id)
        .order_by(Note.created_at.asc(), Note.id.asc())
    )
    return db.execute(query).scalars().all()


def get_note_for_user(db: Session, user_id: int, note_id: int) -> Note | None:
    logger.debug(
        "Fetching note for user", extra={"user_id": user_id, "note_id": note_id}
    )
    query = select(Note).where(Note.user_id == user_id, Note.id == note_id)
    return db.execute(query).scalar_one_or_none()


def get_note_by_id(db: Session, note_id: int) -> Note | None:
    logger.debug("Fetching note by id", extra={"note_id": note_id})
    return db.get(Note, note_id)


def update_note(
    db: Session,
    note: Note,
    text: str | None,
    generated_by_ai: bool | None,
) -> Note:
    logger.debug(
        "Updating note",
        extra={
            "note_id": note.id,
            "text_provided": text is not None,
            "generated_by_ai": generated_by_ai,
        },
    )
    if text is not None:
        note.text = text
    if generated_by_ai is not None:
        note.generated_by_ai = bool(generated_by_ai)

    db.commit()
    db.refresh(note)

    logger.debug("Updated note", extra={"note_id": note.id})
    return note


def delete_note(db: Session, note: Note) -> None:
    logger.debug("Deleting note", extra={"note_id": note.id})
    db.delete(note)
    db.commit()


def search_notes(
    db: Session, user_id: int, q: str, page: int, per_page: int
) -> NoteSearchResponse:

    query = (
        select(Note, Video)
        .join(Video, Video.video_id == Note.video_id)
        .where(Note.user_id == user_id, Note.text.icontains(q, autoescape=True))
    )
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(
        query.order_by(Note.updated_at.desc(), Note.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    ).all()
    items = []
    for note, video in rows:
        text = note.text or ""
        match = text.lower().find(q.lower())
        start = max(0, match - 80)
        end = min(len(text), max(start + 240, match + len(q)))
        excerpt = (
            ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")
        )
        items.append(
            NoteSearchItem(
                id=note.id,
                video_id=note.video_id,
                title=video.title,
                metadata=video.video_metadata,
                timestamp=note.timestamp,
                generated_by_ai=note.generated_by_ai,
                excerpt=excerpt,
            )
        )
    return NoteSearchResponse(
        notes=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )
