import json
import logging
import boto3

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.config import settings
from src.internal.scheduling import schedule_video_tasks
from src.notes.models import Note
from src.videos.models import Video
from src.videos import service as videos_service
from src.credits import service as credits_service

logger = logging.getLogger(__name__)


def get_or_create_video(
    db: Session, video_id: str, video_title: str | None
) -> tuple[Video, bool]:
    logger.debug(
        "Get or create video",
        extra={"video_id": video_id, "title_provided": video_title is not None},
    )
    video = videos_service.get_video_by_id(db, video_id)
    if video:
        logger.debug("Video exists", extra={"video_id": video_id})
        if video_title and not video.title:
            video.title = video_title
            db.commit()
            db.refresh(video)
            logger.debug("Updated video title", extra={"video_id": video_id})
        schedule_video_tasks(db, video)
        return video, False

    video = Video(video_id=video_id, title=video_title)
    db.add(video)
    db.commit()
    db.refresh(video)
    schedule_video_tasks(db, video)
    logger.debug("Created video", extra={"video_id": video_id})
    return video, True


def push_note_to_sqs(note: Note) -> None:
    bucket_url = settings.sqs_ai_note_queue_url
    if not bucket_url:
        logger.warning("SQS_AI_NOTE_QUEUE_URL not configured")
        return

    try:
        client_kwargs = {"region_name": settings.aws_region or "ap-south-1"}
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        sqs = boto3.client("sqs", **client_kwargs)
        # Format payload to match what ai-note.py expects
        # ai-note.py expects:
        # {
        #    "id": note.id,
        #    "video_id": note.video_id,
        #    "timestamp": note.timestamp,
        #    "user_id": note.user_id
        # }
        payload = {
            "id": note.id,
            "video_id": note.video_id,
            "timestamp": note.timestamp,
            "user_id": note.user_id,
        }

        sqs.send_message(QueueUrl=bucket_url, MessageBody=json.dumps(payload))
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


def list_notes_for_video(db: Session, user_id: int, video_id: str) -> list[Note]:
    logger.debug("Listing notes", extra={"user_id": user_id, "video_id": video_id})
    query = (
        select(Note)
        .where(Note.user_id == user_id, Note.video_id == video_id)
        .order_by(Note.created_at.asc(), Note.id.asc())
    )
    return db.execute(query).scalars().all()


def get_note_for_user(db: Session, user_id: int, note_id: int) -> Note | None:
    logger.debug("Fetching note for user", extra={"user_id": user_id, "note_id": note_id})
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
