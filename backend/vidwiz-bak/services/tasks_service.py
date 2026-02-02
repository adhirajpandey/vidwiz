from datetime import datetime, timedelta
import time

from sqlalchemy.orm.attributes import flag_modified

from vidwiz.shared.config import (
    FETCH_METADATA_IN_PROGRESS_TIMEOUT,
    FETCH_METADATA_MAX_RETRIES,
    FETCH_METADATA_TASK_TYPE,
    FETCH_TRANSCRIPT_IN_PROGRESS_TIMEOUT,
    FETCH_TRANSCRIPT_MAX_RETRIES,
    FETCH_TRANSCRIPT_TASK_TYPE,
)
from vidwiz.shared.errors import BadRequestError, ForbiddenError, NotFoundError
from vidwiz.shared.logging import get_logger
from vidwiz.shared.models import Task, TaskStatus, Video, db
from vidwiz.shared.utils import store_transcript_in_s3

logger = get_logger("vidwiz.services.tasks_service")


def _poll_for_task(
    task_type: str,
    timeout: int,
    poll_interval: int,
    max_retries: int,
    in_progress_timeout: int,
    worker_user_id: int | None,
    testing: bool,
):
    start_time = time.time()

    while time.time() - start_time < timeout:
        stale_cutoff = datetime.now() - timedelta(seconds=in_progress_timeout)

        task_query = Task.query.filter(Task.task_type == task_type).filter(
            (Task.status == TaskStatus.PENDING)
            | (
                (Task.status == TaskStatus.FAILED)
                & (Task.retry_count < max_retries)
            )
            | (
                (Task.status == TaskStatus.IN_PROGRESS)
                & (Task.started_at < stale_cutoff)
            )
        )

        if testing:
            task = task_query.first()
        else:
            task = task_query.with_for_update(skip_locked=True).first()

        if task:
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now()
            task.retry_count += 1

            task.worker_details = task.worker_details or {}
            task.worker_details["worker_user_id"] = worker_user_id

            db.session.commit()
            return task

        time.sleep(poll_interval)

    return None


def get_transcript_task(
    timeout: int,
    poll_interval: int,
    worker_user_id: int | None,
    testing: bool,
):
    return _poll_for_task(
        FETCH_TRANSCRIPT_TASK_TYPE,
        timeout,
        poll_interval,
        FETCH_TRANSCRIPT_MAX_RETRIES,
        FETCH_TRANSCRIPT_IN_PROGRESS_TIMEOUT,
        worker_user_id,
        testing,
    )


def get_metadata_task(
    timeout: int,
    poll_interval: int,
    worker_user_id: int | None,
    testing: bool,
):
    return _poll_for_task(
        FETCH_METADATA_TASK_TYPE,
        timeout,
        poll_interval,
        FETCH_METADATA_MAX_RETRIES,
        FETCH_METADATA_IN_PROGRESS_TIMEOUT,
        worker_user_id,
        testing,
    )


def _get_task_or_raise(task_id: int):
    task = Task.query.get(task_id)
    if not task:
        raise NotFoundError("Task not found")
    return task


def _validate_task_for_submit(task, video_id: str, worker_user_id: int | None):
    if task.task_details.get("video_id") != video_id:
        raise BadRequestError("Task video_id mismatch")

    if task.status != TaskStatus.IN_PROGRESS:
        raise BadRequestError("Task is not in progress")

    task_worker_id = task.worker_details.get("worker_user_id", None)
    if task_worker_id != worker_user_id:
        raise ForbiddenError("Task belongs to a different worker")


def submit_transcript_result(
    task_id: int,
    video_id: str,
    success: bool,
    transcript: list | None,
    error_message: str | None,
    worker_user_id: int | None,
):
    task = _get_task_or_raise(task_id)
    _validate_task_for_submit(task, video_id, worker_user_id)

    task.completed_at = datetime.now()

    if success:
        task.status = TaskStatus.COMPLETED

        if transcript:
            try:
                store_transcript_in_s3(video_id, transcript)
                video = Video.query.filter_by(video_id=video_id).first()
                if video:
                    video.transcript_available = True
            except Exception as s3_error:
                logger.error(f"Error storing transcript in S3: {s3_error}")
    else:
        if task.retry_count >= FETCH_TRANSCRIPT_MAX_RETRIES:
            task.status = TaskStatus.FAILED
        else:
            task.status = TaskStatus.PENDING
            task.started_at = None

        if task.worker_details is None:
            task.worker_details = {}

        task.worker_details["error_message"] = (
            error_message or "Unknown error occurred"
        )
        task.worker_details["retry_attempt"] = task.retry_count
        flag_modified(task, "worker_details")

    db.session.commit()
    return task


def submit_metadata_result(
    task_id: int,
    video_id: str,
    success: bool,
    metadata: dict | None,
    error_message: str | None,
    worker_user_id: int | None,
):
    task = _get_task_or_raise(task_id)
    _validate_task_for_submit(task, video_id, worker_user_id)

    task.completed_at = datetime.now()

    if success:
        task.status = TaskStatus.COMPLETED

        if metadata:
            try:
                video = Video.query.filter_by(video_id=video_id).first()
                if video:
                    video.video_metadata = metadata
                    logger.info(
                        f"Updated video_metadata for video_id={video_id}"
                    )
            except Exception as metadata_error:
                logger.error(f"Error storing metadata: {metadata_error}")
    else:
        if task.retry_count >= FETCH_METADATA_MAX_RETRIES:
            task.status = TaskStatus.FAILED
        else:
            task.status = TaskStatus.PENDING
            task.started_at = None

        if task.worker_details is None:
            task.worker_details = {}

        task.worker_details["error_message"] = (
            error_message or "Unknown error occurred"
        )
        task.worker_details["retry_attempt"] = task.retry_count
        flag_modified(task, "worker_details")

    db.session.commit()
    return task
