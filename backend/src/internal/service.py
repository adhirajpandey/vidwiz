from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from src.exceptions import BadRequestError, NotFoundError
from src.internal import constants as internal_constants
from src.internal.models import Task, TaskStatus
from src.moments import service as moments_service
from src.moments.models import Moment, ResolveStatus
from src.search.chunks import replace_chunks
from src.internal.schemas import TaskResultRequest
from src.videos import service as videos_service
from src.videos.models import Video
from src import transcripts

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

        # End the read transaction so the connection is not held idle while waiting.
        db.commit()
        time.sleep(poll_interval)

    logger.debug("No task available", extra={"task_type": task_type})
    return None


def submit_task_result(
    db: Session,
    task_id: int,
    result: TaskResultRequest,
) -> Task:
    task = db.get(Task, task_id)
    if not task:
        raise NotFoundError("Task not found")
    logger.debug(
        "Submitting task result",
        extra={
            "task_id": task_id,
            "task_type": task.task_type,
            "success": result.success,
        },
    )
    if task.status != TaskStatus.IN_PROGRESS:
        raise BadRequestError("Task is not in progress")

    task_type = task.task_type
    if task_type == internal_constants.RESOLVE_TITLE_TASK_TYPE:
        _validate_resolve_result(result)
    elif task_type in (
        internal_constants.FETCH_TRANSCRIPT_TASK_TYPE,
        internal_constants.FETCH_METADATA_TASK_TYPE,
    ):
        _validate_video_result(task, result)
    else:
        raise BadRequestError("Unsupported task type")

    task.completed_at = datetime.utcnow()
    if result.success:
        task.status = TaskStatus.COMPLETED
        _apply_success(db, task, result)
    else:
        final = task.retry_count >= internal_constants.TASK_MAX_RETRIES
        if final:
            task.status = TaskStatus.FAILED
            _apply_final_failure(db, task)
        else:
            task.status = TaskStatus.PENDING
            task.started_at = None
        task.worker_details = {
            **(task.worker_details or {}),
            "error_message": result.error_message or "Unknown error occurred",
            "retry_attempt": task.retry_count,
        }

    db.commit()
    db.refresh(task)
    logger.debug("Task updated", extra={"task_id": task.id, "status": task.status})
    return task


def _validate_video_result(task: Task, result: TaskResultRequest) -> None:
    if not result.video_id:
        raise BadRequestError("video_id is required for video tasks")
    if task.task_details and task.task_details.get("video_id") != result.video_id:
        raise BadRequestError("Task video_id mismatch")
    is_transcript = task.task_type == internal_constants.FETCH_TRANSCRIPT_TASK_TYPE
    if result.resolved is not None:
        raise BadRequestError("Resolved video is only valid for title tasks")
    if is_transcript and result.metadata:
        raise BadRequestError("Metadata payload is not valid for transcript tasks")
    if not is_transcript and result.transcript:
        raise BadRequestError("Transcript payload is not valid for metadata tasks")


def _validate_resolve_result(result: TaskResultRequest) -> None:
    if result.transcript or result.metadata:
        raise BadRequestError("Title tasks only accept a resolved video")
    if result.success and result.resolved is None:
        raise BadRequestError("A successful title task needs a resolved video")


def _task_moment(db: Session, task: Task) -> Moment | None:
    moment_id = (task.task_details or {}).get("moment_id")
    return db.get(Moment, moment_id) if moment_id else None


def _apply_success(db: Session, task: Task, result: TaskResultRequest) -> None:
    if task.task_type == internal_constants.RESOLVE_TITLE_TASK_TYPE:
        moment = _task_moment(db, task)
        if moment is not None and moment.resolve_status == ResolveStatus.RESOLVING:
            moments_service.complete_resolution(
                db, moment, result.resolved.video_id, result.resolved.title
            )
        return

    video = videos_service.get_video_by_id(db, result.video_id)
    if task.task_type == internal_constants.FETCH_TRANSCRIPT_TASK_TYPE:
        if result.transcript:
            store_transcript_in_s3(result.video_id, result.transcript)
            moments_service.on_transcript_stored(db, result.video_id, result.transcript)
            replace_chunks(db, result.video_id, result.transcript)
        if video:
            video.transcript_available = True
    elif video and result.metadata:
        _apply_metadata(video, result.metadata)


def _apply_metadata(video: Video, metadata: dict) -> None:
    video.video_metadata = metadata
    # Captures by ID carry no title; metadata supplies it.
    if not video.title and metadata.get("title"):
        video.title = metadata["title"]


def _apply_final_failure(db: Session, task: Task) -> None:
    if task.task_type == internal_constants.RESOLVE_TITLE_TASK_TYPE:
        moment = _task_moment(db, task)
        if moment is not None and moment.resolve_status == ResolveStatus.RESOLVING:
            moments_service.fail_resolution(db, moment)
    elif task.task_type == internal_constants.FETCH_TRANSCRIPT_TASK_TYPE:
        video_id = (task.task_details or {}).get("video_id")
        if video_id:
            moments_service.on_transcript_unavailable(db, video_id)


store_transcript_in_s3 = transcripts.store_transcript


def store_transcript(db: Session, video_id: str, transcript: list[dict]) -> Video:
    logger.debug("Storing transcript", extra={"video_id": video_id})
    video = videos_service.get_or_create_video(db, video_id)
    store_transcript_in_s3(video_id, transcript)
    moments_service.on_transcript_stored(db, video_id, transcript)
    replace_chunks(db, video_id, transcript)
    video.transcript_available = True
    db.commit()
    db.refresh(video)
    return video


def store_metadata(db: Session, video_id: str, metadata: dict) -> Video:
    logger.debug("Storing metadata", extra={"video_id": video_id})
    video = videos_service.get_or_create_video(db, video_id)
    _apply_metadata(video, metadata)
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


def get_video(db: Session, video_id: str) -> Video | None:
    logger.debug("Fetching video", extra={"video_id": video_id})
    return videos_service.get_video_by_id(db, video_id)
