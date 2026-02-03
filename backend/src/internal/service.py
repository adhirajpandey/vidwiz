from __future__ import annotations

import json
import time
from datetime import datetime, timedelta

import boto3
from sqlalchemy import Boolean, and_, cast, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from src.auth.models import User
from src.exceptions import BadRequestError, ForbiddenError, NotFoundError
from src.internal import constants as internal_constants
from src.internal.models import Task, TaskStatus
from src.internal.scheduling import create_task_idempotent, schedule_video_tasks
from src.notes.models import Note
from src.notes import service as notes_service
from src.videos import service as videos_service
from src.videos.models import Video
from src.conversations.config import conversations_settings


def poll_for_task(
    db: Session,
    task_type: str,
    timeout: int,
    poll_interval: int,
    max_retries: int,
    in_progress_timeout: int,
    worker_user_id: int | None,
) -> Task | None:
    start_time = time.time()
    use_lock = db.get_bind().dialect.name != "sqlite"

    while time.time() - start_time < timeout:
        stale_cutoff = datetime.utcnow() - timedelta(seconds=in_progress_timeout)

        criteria = or_(
            Task.status == TaskStatus.PENDING,
            and_(Task.status == TaskStatus.FAILED, Task.retry_count < max_retries),
            and_(
                Task.status == TaskStatus.IN_PROGRESS,
                or_(Task.started_at.is_(None), Task.started_at < stale_cutoff),
            ),
        )

        query = select(Task).where(Task.task_type == task_type, criteria).order_by(Task.id.asc())
        if use_lock:
            query = query.with_for_update(skip_locked=True)

        task = db.execute(query).scalars().first()
        if task:
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.utcnow()
            task.retry_count = (task.retry_count or 0) + 1

            worker_details = task.worker_details or {}
            worker_details["worker_user_id"] = worker_user_id
            task.worker_details = worker_details
            flag_modified(task, "worker_details")

            db.commit()
            db.refresh(task)
            return task

        time.sleep(poll_interval)

    return None


def submit_task_result(
    db: Session,
    task_id: int,
    video_id: str,
    success: bool,
    transcript: list[dict] | None,
    metadata: dict | None,
    error_message: str | None,
    worker_user_id: int | None,
) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise NotFoundError("Task not found")

    if task.task_details and task.task_details.get("video_id") != video_id:
        raise BadRequestError("Task video_id mismatch")

    if task.status != TaskStatus.IN_PROGRESS:
        raise BadRequestError("Task is not in progress")

    task_worker_id = (task.worker_details or {}).get("worker_user_id")
    if task_worker_id != worker_user_id:
        raise ForbiddenError("Task belongs to a different worker")

    if task.task_type == internal_constants.FETCH_TRANSCRIPT_TASK_TYPE and metadata:
        raise BadRequestError("Metadata payload is not valid for transcript tasks")

    if task.task_type == internal_constants.FETCH_METADATA_TASK_TYPE and transcript:
        raise BadRequestError("Transcript payload is not valid for metadata tasks")

    if task.task_type == internal_constants.FETCH_TRANSCRIPT_TASK_TYPE:
        return _submit_transcript_result(
            db,
            task,
            video_id,
            success,
            transcript,
            error_message,
        )

    if task.task_type == internal_constants.FETCH_METADATA_TASK_TYPE:
        return _submit_metadata_result(
            db,
            task,
            video_id,
            success,
            metadata,
            error_message,
        )

    raise BadRequestError("Unsupported task type")


def _submit_transcript_result(
    db: Session,
    task: Task,
    video_id: str,
    success: bool,
    transcript: list[dict] | None,
    error_message: str | None,
) -> Task:
    task.completed_at = datetime.utcnow()

    if success:
        task.status = TaskStatus.COMPLETED

        if transcript:
            store_transcript_in_s3(video_id, transcript)
        video = videos_service.get_video_by_id(db, video_id)
        if video:
            video.transcript_available = True
    else:
        if task.retry_count >= internal_constants.FETCH_TRANSCRIPT_MAX_RETRIES:
            task.status = TaskStatus.FAILED
        else:
            task.status = TaskStatus.PENDING
            task.started_at = None

        worker_details = task.worker_details or {}
        worker_details["error_message"] = error_message or "Unknown error occurred"
        worker_details["retry_attempt"] = task.retry_count
        task.worker_details = worker_details
        flag_modified(task, "worker_details")

    db.commit()
    db.refresh(task)
    return task


def _submit_metadata_result(
    db: Session,
    task: Task,
    video_id: str,
    success: bool,
    metadata: dict | None,
    error_message: str | None,
) -> Task:
    task.completed_at = datetime.utcnow()

    if success:
        task.status = TaskStatus.COMPLETED
        if metadata:
            video = videos_service.get_video_by_id(db, video_id)
            if video:
                video.video_metadata = metadata
    else:
        if task.retry_count >= internal_constants.FETCH_METADATA_MAX_RETRIES:
            task.status = TaskStatus.FAILED
        else:
            task.status = TaskStatus.PENDING
            task.started_at = None

        worker_details = task.worker_details or {}
        worker_details["error_message"] = error_message or "Unknown error occurred"
        worker_details["retry_attempt"] = task.retry_count
        task.worker_details = worker_details
        flag_modified(task, "worker_details")

    db.commit()
    db.refresh(task)
    return task


def store_transcript_in_s3(video_id: str, transcript: list[dict]) -> None:
    bucket = conversations_settings.s3_bucket_name
    if not bucket:
        return
    if not (
        conversations_settings.aws_access_key_id
        and conversations_settings.aws_secret_access_key
        and conversations_settings.aws_region
    ):
        return

    transcript_key = f"transcripts/{video_id}.json"
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=conversations_settings.aws_access_key_id,
        aws_secret_access_key=conversations_settings.aws_secret_access_key,
        region_name=conversations_settings.aws_region,
    )
    s3_client.put_object(
        Bucket=bucket,
        Key=transcript_key,
        Body=json.dumps(transcript).encode("utf-8"),
        ContentType="application/json",
    )


def upsert_video(db: Session, video_id: str) -> Video:
    video = videos_service.get_video_by_id(db, video_id)
    if video:
        return video

    video = Video(video_id=video_id)
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def store_transcript(db: Session, video_id: str, transcript: list[dict]) -> Video:
    video = upsert_video(db, video_id)
    store_transcript_in_s3(video_id, transcript)
    video.transcript_available = True
    db.commit()
    db.refresh(video)
    return video


def store_metadata(db: Session, video_id: str, metadata: dict) -> Video:
    video = upsert_video(db, video_id)
    video.video_metadata = metadata
    db.commit()
    db.refresh(video)
    return video


def store_summary(db: Session, video_id: str, summary: str | None) -> Video:
    video = upsert_video(db, video_id)
    if summary is not None:
        video.summary = summary
    db.commit()
    db.refresh(video)
    return video


def fetch_ai_note_task_notes(db: Session, video_id: str) -> tuple[Video | None, list[Note]]:
    video = videos_service.get_video_by_id(db, video_id)
    if not video:
        return None, []

    is_sqlite = db.get_bind().dialect.name == "sqlite"
    if is_sqlite:
        results = db.execute(
            select(Note, User)
            .join(User, Note.user_id == User.id)
            .where(
                Note.video_id == video_id,
                or_(Note.text.is_(None), Note.text == ""),
            )
            .order_by(Note.created_at.asc(), Note.id.asc())
        ).all()
        notes = [
            note
            for note, user in results
            if user.profile_data and user.profile_data.get("ai_notes_enabled", False)
        ]
        return video, notes

    notes = (
        db.execute(
            select(Note)
            .join(User, Note.user_id == User.id)
            .where(
                Note.video_id == video_id,
                cast(User.profile_data["ai_notes_enabled"].as_boolean(), Boolean).is_(
                    True
                ),
                or_(Note.text.is_(None), Note.text == ""),
            )
            .order_by(Note.created_at.asc(), Note.id.asc())
        )
        .scalars()
        .all()
    )
    return video, notes


def get_video(db: Session, video_id: str) -> Video | None:
    return videos_service.get_video_by_id(db, video_id)


def update_note(
    db: Session,
    note_id: int,
    text: str | None,
    generated_by_ai: bool | None,
) -> Note | None:
    # We need to find the user_id for the note to use get_note_for_user or just get it directly.
    # Since this is internal admin, we can get note directly by ID.
    note = notes_service.get_note_by_id(db, note_id)
    if not note:
        return None

    return notes_service.update_note(db, note, text, generated_by_ai)
