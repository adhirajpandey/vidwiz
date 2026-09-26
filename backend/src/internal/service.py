from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta

import boto3
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from src.auth.models import User
from src.exceptions import BadRequestError, NotFoundError
from src.internal import constants as internal_constants
from src.internal.models import Task, TaskStatus
from src.notes.models import Note
from src.notes import service as notes_service
from src.videos import service as videos_service
from src.videos.models import Video
from src.config import settings

logger = logging.getLogger(__name__)


def poll_for_task(
    db: Session,
    task_type: str,
    timeout: int,
    poll_interval: int = internal_constants.TASK_POLL_INTERVAL,
) -> Task | None:
    logger.debug(
        "Polling for task",
        extra={"task_type": task_type, "timeout": timeout},
    )
    start_time = time.time()

    while time.time() - start_time < timeout:
        stale_cutoff = datetime.utcnow() - timedelta(
            seconds=internal_constants.TASK_IN_PROGRESS_TIMEOUT
        )
        criteria = or_(
            Task.status == TaskStatus.PENDING,
            and_(
                Task.status == TaskStatus.FAILED,
                Task.retry_count < internal_constants.TASK_MAX_RETRIES,
            ),
            and_(
                Task.status == TaskStatus.IN_PROGRESS,
                or_(Task.started_at.is_(None), Task.started_at < stale_cutoff),
            ),
        )
        # SQLite ignores FOR UPDATE, so tests exercise the production query.
        query = (
            select(Task)
            .where(Task.task_type == task_type, criteria)
            .order_by(Task.id.asc())
            .with_for_update(skip_locked=True)
        )

        task = db.execute(query).scalars().first()
        if task:
            logger.debug(
                "Claimed task", extra={"task_id": task.id, "task_type": task_type}
            )
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.utcnow()
            task.retry_count = (task.retry_count or 0) + 1
            db.commit()
            db.refresh(task)
            return task

        time.sleep(poll_interval)

    logger.debug("No task available", extra={"task_type": task_type})
    return None


def submit_task_result(
    db: Session,
    task_id: int,
    video_id: str,
    success: bool,
    transcript: list[dict] | None,
    metadata: dict | None,
    error_message: str | None,
) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise NotFoundError("Task not found")
    logger.debug(
        "Submitting task result",
        extra={"task_id": task_id, "task_type": task.task_type, "success": success},
    )

    if task.task_details and task.task_details.get("video_id") != video_id:
        raise BadRequestError("Task video_id mismatch")

    if task.status != TaskStatus.IN_PROGRESS:
        raise BadRequestError("Task is not in progress")

    is_transcript = task.task_type == internal_constants.FETCH_TRANSCRIPT_TASK_TYPE
    is_metadata = task.task_type == internal_constants.FETCH_METADATA_TASK_TYPE
    if not (is_transcript or is_metadata):
        raise BadRequestError("Unsupported task type")
    if is_transcript and metadata:
        raise BadRequestError("Metadata payload is not valid for transcript tasks")
    if is_metadata and transcript:
        raise BadRequestError("Transcript payload is not valid for metadata tasks")

    task.completed_at = datetime.utcnow()
    if success:
        task.status = TaskStatus.COMPLETED
        if is_transcript and transcript:
            store_transcript_in_s3(video_id, transcript)
        video = videos_service.get_video_by_id(db, video_id)
        if video and is_transcript:
            video.transcript_available = True
        elif video and metadata:
            video.video_metadata = metadata
    else:
        if task.retry_count >= internal_constants.TASK_MAX_RETRIES:
            task.status = TaskStatus.FAILED
        else:
            task.status = TaskStatus.PENDING
            task.started_at = None
        task.worker_details = {
            **(task.worker_details or {}),
            "error_message": error_message or "Unknown error occurred",
            "retry_attempt": task.retry_count,
        }

    db.commit()
    db.refresh(task)
    logger.debug("Task updated", extra={"task_id": task.id, "status": task.status})
    return task


def store_transcript_in_s3(video_id: str, transcript: list[dict]) -> None:
    logger.debug("Storing transcript in S3", extra={"video_id": video_id})
    bucket = settings.s3_transcript_bucket_name
    if not bucket:
        logger.debug("S3 bucket not configured", extra={"video_id": video_id})
        return
    transcript_key = f"transcripts/{video_id}.json"
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )
    s3_client.put_object(
        Bucket=bucket,
        Key=transcript_key,
        Body=json.dumps(transcript).encode("utf-8"),
        ContentType="application/json",
    )
    logger.debug("Stored transcript in S3", extra={"video_id": video_id})


def store_transcript(db: Session, video_id: str, transcript: list[dict]) -> Video:
    logger.debug("Storing transcript", extra={"video_id": video_id})
    video = videos_service.get_or_create_video(db, video_id)
    store_transcript_in_s3(video_id, transcript)
    video.transcript_available = True
    db.commit()
    db.refresh(video)
    return video


def store_metadata(db: Session, video_id: str, metadata: dict) -> Video:
    logger.debug("Storing metadata", extra={"video_id": video_id})
    video = videos_service.get_or_create_video(db, video_id)
    video.video_metadata = metadata
    db.commit()
    db.refresh(video)
    return video


def store_summary(
    db: Session,
    video_id: str,
    summary: str | None,
    miscellaneous_data: dict | None = None,
) -> Video:
    logger.debug(
        "Storing summary",
        extra={"video_id": video_id, "has_summary": summary is not None},
    )
    video = videos_service.get_or_create_video(db, video_id)
    if summary is not None:
        video.summary = summary
    if miscellaneous_data:
        video.miscellaneous_data = {
            **(video.miscellaneous_data or {}),
            **miscellaneous_data,
        }
    db.commit()
    db.refresh(video)
    return video


def fetch_ai_note_task_notes(
    db: Session, video_id: str
) -> tuple[Video | None, list[Note]]:
    logger.debug("Fetching AI note task notes", extra={"video_id": video_id})
    video = videos_service.get_video_by_id(db, video_id)
    if not video:
        return None, []

    notes = (
        db.execute(
            select(Note)
            .join(User, Note.user_id == User.id)
            .where(
                Note.video_id == video_id,
                or_(Note.text.is_(None), Note.text == ""),
                # Portable JSON predicate: SQLite tests run the production query.
                User.profile_data["ai_notes_enabled"].as_boolean().is_(True),
            )
            .order_by(Note.created_at.asc(), Note.id.asc())
        )
        .scalars()
        .all()
    )
    return video, notes


def get_video(db: Session, video_id: str) -> Video | None:
    logger.debug("Fetching video", extra={"video_id": video_id})
    return videos_service.get_video_by_id(db, video_id)


def update_note(
    db: Session,
    note_id: int,
    text: str | None,
    generated_by_ai: bool | None,
) -> Note | None:
    logger.debug("Updating note via internal", extra={"note_id": note_id})
    # We need to find the user_id for the note to use get_note_for_user or just get it directly.
    # Since this is internal admin, we can get note directly by ID.
    note = notes_service.get_note_by_id(db, note_id)
    if not note:
        return None

    return notes_service.update_note(db, note, text, generated_by_ai)
