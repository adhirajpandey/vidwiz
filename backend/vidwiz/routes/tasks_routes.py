from flask import Blueprint, jsonify, request, current_app
from vidwiz.shared.models import Task, TaskStatus, db, Video
from vidwiz.shared.utils import store_transcript_in_s3, jwt_or_admin_required, require_json_body
from vidwiz.shared.schemas import TranscriptResult, MetadataResult, TaskRetrievedResponse, TaskTimeoutResponse, TaskSubmitResponse
from vidwiz.shared.errors import (
    handle_validation_error,
    NotFoundError,
    BadRequestError,
    ForbiddenError,
)
from vidwiz.shared.config import (
    TRANSCRIPT_TASK_REQUEST_DEFAULT_TIMEOUT,
    TRANSCRIPT_TASK_REQUEST_MAX_TIMEOUT,
    TRANSCRIPT_POLL_INTERVAL,
    FETCH_TRANSCRIPT_TASK_TYPE,
    FETCH_TRANSCRIPT_MAX_RETRIES,
    FETCH_TRANSCRIPT_IN_PROGRESS_TIMEOUT,
    METADATA_TASK_REQUEST_DEFAULT_TIMEOUT,
    METADATA_TASK_REQUEST_MAX_TIMEOUT,
    METADATA_POLL_INTERVAL,
    FETCH_METADATA_TASK_TYPE,
    FETCH_METADATA_MAX_RETRIES,
    FETCH_METADATA_IN_PROGRESS_TIMEOUT,
)
from pydantic import ValidationError
from datetime import datetime, timedelta
import time
from sqlalchemy.orm.attributes import flag_modified
from vidwiz.shared.logging import get_logger

logger = get_logger("vidwiz.routes.tasks_routes")


tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.route("/tasks/transcript", methods=["GET"])
@jwt_or_admin_required
def get_transcript_task():
    """
    Endpoint to retrieve a transcript task for processing from the task table.
    """
    timeout = min(
        int(request.args.get("timeout", TRANSCRIPT_TASK_REQUEST_DEFAULT_TIMEOUT)),
        TRANSCRIPT_TASK_REQUEST_MAX_TIMEOUT,
    )

    start_time = time.time()
    logger.info(
        f"Transcript task poll started by user_id={getattr(request, 'user_id', None)} with timeout={timeout}s"
    )

    while time.time() - start_time < timeout:
        # Calculate cutoff time for stale in-progress tasks
        stale_cutoff = datetime.now() - timedelta(
            seconds=FETCH_TRANSCRIPT_IN_PROGRESS_TIMEOUT
        )

        # Searching for pending, retryable failed, or stale in-progress transcript tasks
        task_query = Task.query.filter(
            Task.task_type == FETCH_TRANSCRIPT_TASK_TYPE
        ).filter(
            (Task.status == TaskStatus.PENDING)
            | (
                (Task.status == TaskStatus.FAILED)
                & (Task.retry_count < FETCH_TRANSCRIPT_MAX_RETRIES)
            )
            | (
                (Task.status == TaskStatus.IN_PROGRESS)
                & (Task.started_at < stale_cutoff)
            )
        )

        # Apply row-level locking to avoid multiple workers claiming the same task
        if current_app.config.get("TESTING"):
            # SQLite (used in tests) lacks SELECT FOR UPDATE
            task = task_query.first()
        else:
            task = task_query.with_for_update(skip_locked=True).first()

        if task:
            # If a task is found, update its status to IN_PROGRESS and assign to worker
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now()
            task.retry_count += 1

            # Store worker information
            task.worker_details = task.worker_details or {}
            task.worker_details["worker_user_id"] = request.user_id

            db.session.commit()
            logger.info(
                f"Assigned transcript task task_id={task.id} to user_id={request.user_id}, retry_count={task.retry_count}"
            )

            return jsonify(
                TaskRetrievedResponse(
                    task_id=task.id,
                    task_type=task.task_type,
                    task_details=task.task_details,
                    retry_count=task.retry_count,
                    message="Transcript task retrieved successfully",
                ).model_dump()
            ), 200

        time.sleep(TRANSCRIPT_POLL_INTERVAL)

    logger.info("No transcript tasks available within timeout window")
    return jsonify(
        TaskTimeoutResponse(
            message="No transcript tasks available for processing",
            timeout=True,
        ).model_dump()
    ), 204


@tasks_bp.route("/tasks/transcript", methods=["POST"])
@jwt_or_admin_required
@require_json_body
def submit_transcript_result():
    """
    Endpoint for workers to submit transcript processing results.
    """
    try:
        result_data = TranscriptResult.model_validate(request.json_data)
    except ValidationError as e:
        logger.warning(f"Submit transcript result validation error: {e}")
        return handle_validation_error(e)

    # Find the task
    task = Task.query.get(result_data.task_id)
    if not task:
        logger.warning(f"Transcript task not found task_id={result_data.task_id}")
        raise NotFoundError("Task not found")

    # Verify task belongs to the right video
    if task.task_details.get("video_id") != result_data.video_id:
        logger.warning(
            f"Task {task.id if task else None} video_id mismatch payload={result_data.video_id}"
        )
        raise BadRequestError("Task video_id mismatch")

    # Verify task is in IN_PROGRESS status
    if task.status != TaskStatus.IN_PROGRESS:
        logger.warning(
            f"Task {task.id} not in progress; current status={task.status}"
        )
        raise BadRequestError("Task is not in progress")

    # Verify that the request is coming from the same worker who retrieved the task
    worker_user_id = task.worker_details.get("worker_user_id", None)

    if worker_user_id != request.user_id:
        logger.warning(
            f"Unauthorized submit for task_id={task.id} by user_id={request.user_id}, owner={worker_user_id}"
        )
        raise ForbiddenError("Task belongs to a different worker")

    # Update task based on result
    task.completed_at = datetime.now()

    if result_data.success:
        task.status = TaskStatus.COMPLETED

        # Store transcript in S3 if provided
        if result_data.transcript:
            try:
                store_transcript_in_s3(result_data.video_id, result_data.transcript)
                # Update video transcript_available flag
                video = Video.query.filter_by(video_id=result_data.video_id).first()
                if video:
                    video.transcript_available = True

            except Exception as s3_error:
                logger.error(f"Error storing transcript in S3: {s3_error}")
                # Don't fail the task just because S3 failed

    else:
        # Check if task has reached max retries
        if task.retry_count >= FETCH_TRANSCRIPT_MAX_RETRIES:
            task.status = TaskStatus.FAILED
        else:
            # Reset status to PENDING for retry
            task.status = TaskStatus.PENDING
            task.started_at = None

        # Update worker_details with error information
        if task.worker_details is None:
            task.worker_details = {}

        task.worker_details["error_message"] = (
            result_data.error_message or "Unknown error occurred"
        )
        task.worker_details["retry_attempt"] = task.retry_count

        # Mark the attribute as modified to ensure SQLAlchemy detects the change
        flag_modified(task, "worker_details")

    db.session.commit()
    logger.info(
        f"Transcript result submitted for task_id={task.id}, status={task.status}"
    )

    return jsonify(
        TaskSubmitResponse(
            message="Transcript result submitted successfully",
            task_id=task.id,
            status=task.status.value,
        ).model_dump()
    ), 200


@tasks_bp.route("/tasks/metadata", methods=["GET"])
@jwt_or_admin_required
def get_metadata_task():
    """
    Endpoint to retrieve a metadata task for processing from the task table.
    """
    timeout = min(
        int(request.args.get("timeout", METADATA_TASK_REQUEST_DEFAULT_TIMEOUT)),
        METADATA_TASK_REQUEST_MAX_TIMEOUT,
    )

    start_time = time.time()
    logger.info(
        f"Metadata task poll started by user_id={getattr(request, 'user_id', None)} with timeout={timeout}s"
    )

    while time.time() - start_time < timeout:
        # Calculate cutoff time for stale in-progress tasks
        stale_cutoff = datetime.now() - timedelta(
            seconds=FETCH_METADATA_IN_PROGRESS_TIMEOUT
        )

        # Searching for pending, retryable failed, or stale in-progress metadata tasks
        task_query = Task.query.filter(
            Task.task_type == FETCH_METADATA_TASK_TYPE
        ).filter(
            (Task.status == TaskStatus.PENDING)
            | (
                (Task.status == TaskStatus.FAILED)
                & (Task.retry_count < FETCH_METADATA_MAX_RETRIES)
            )
            | (
                (Task.status == TaskStatus.IN_PROGRESS)
                & (Task.started_at < stale_cutoff)
            )
        )

        # Apply row-level locking to avoid multiple workers claiming the same task
        if current_app.config.get("TESTING"):
            # SQLite (used in tests) lacks SELECT FOR UPDATE
            task = task_query.first()
        else:
            task = task_query.with_for_update(skip_locked=True).first()

        if task:
            # If a task is found, update its status to IN_PROGRESS and assign to worker
            task.status = TaskStatus.IN_PROGRESS
            task.started_at = datetime.now()
            task.retry_count += 1

            # Store worker information
            task.worker_details = task.worker_details or {}
            task.worker_details["worker_user_id"] = request.user_id

            db.session.commit()
            logger.info(
                f"Assigned metadata task task_id={task.id} to user_id={request.user_id}, retry_count={task.retry_count}"
            )

            return jsonify(
                TaskRetrievedResponse(
                    task_id=task.id,
                    task_type=task.task_type,
                    task_details=task.task_details,
                    retry_count=task.retry_count,
                    message="Metadata task retrieved successfully",
                ).model_dump()
            ), 200

        time.sleep(METADATA_POLL_INTERVAL)

    logger.info("No metadata tasks available within timeout window")
    return jsonify(
        TaskTimeoutResponse(
            message="No metadata tasks available for processing",
            timeout=True,
        ).model_dump()
    ), 204


@tasks_bp.route("/tasks/metadata", methods=["POST"])
@jwt_or_admin_required
@require_json_body
def submit_metadata_result():
    """
    Endpoint for workers to submit metadata processing results.
    """
    try:
        result_data = MetadataResult.model_validate(request.json_data)
    except ValidationError as e:
        logger.warning(f"Submit metadata result validation error: {e}")
        return handle_validation_error(e)

    # Find the task
    task = Task.query.get(result_data.task_id)

    if not task:
        logger.warning(f"Metadata task not found task_id={result_data.task_id}")
        raise NotFoundError("Task not found")

    # Verify task belongs to the right video
    if task.task_details.get("video_id") != result_data.video_id:
        logger.warning(
            f"Task {task.id if task else None} video_id mismatch payload={result_data.video_id}"
        )
        raise BadRequestError("Task video_id mismatch")

    # Verify task is in IN_PROGRESS status
    if task.status != TaskStatus.IN_PROGRESS:
        logger.warning(
            f"Task {task.id} not in progress; current status={task.status}"
        )
        raise BadRequestError("Task is not in progress")

    # Verify that the request is coming from the same worker who retrieved the task
    worker_user_id = task.worker_details.get("worker_user_id", None)

    if worker_user_id != request.user_id:
        logger.warning(
            f"Unauthorized submit for task_id={task.id} by user_id={request.user_id}, owner={worker_user_id}"
        )
        raise ForbiddenError("Task belongs to a different worker")

    # Update task based on result
    task.completed_at = datetime.now()

    if result_data.success:
        task.status = TaskStatus.COMPLETED

        # Store metadata in video record
        if result_data.metadata:
            try:
                video = Video.query.filter_by(video_id=result_data.video_id).first()
                if video:
                    video.video_metadata = result_data.metadata
                    logger.info(
                        f"Updated video_metadata for video_id={result_data.video_id}"
                    )
            except Exception as metadata_error:
                logger.error(f"Error storing metadata: {metadata_error}")
                # Don't fail the task just because metadata storage failed

    else:
        # Check if task has reached max retries
        if task.retry_count >= FETCH_METADATA_MAX_RETRIES:
            task.status = TaskStatus.FAILED
        else:
            # Reset status to PENDING for retry
            task.status = TaskStatus.PENDING
            task.started_at = None

        # Update worker_details with error information
        if task.worker_details is None:
            task.worker_details = {}

        task.worker_details["error_message"] = (
            result_data.error_message or "Unknown error occurred"
        )
        task.worker_details["retry_attempt"] = task.retry_count

        # Mark the attribute as modified to ensure SQLAlchemy detects the change
        flag_modified(task, "worker_details")

    db.session.commit()
    logger.info(
        f"Metadata result submitted for task_id={task.id}, status={task.status}"
    )

    return jsonify(
        TaskSubmitResponse(
            message="Metadata result submitted successfully",
            task_id=task.id,
            status=task.status.value,
        ).model_dump()
    ), 200

