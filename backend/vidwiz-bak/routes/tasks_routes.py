from flask import Blueprint, jsonify, request, current_app
from vidwiz.shared.utils import jwt_or_admin_required, require_json_body
from vidwiz.shared.schemas import (
    TranscriptResult,
    MetadataResult,
    TaskRetrievedResponse,
    TaskTimeoutResponse,
    TaskSubmitResponse,
)
from vidwiz.shared.errors import handle_validation_error
from vidwiz.shared.config import (
    TRANSCRIPT_TASK_REQUEST_DEFAULT_TIMEOUT,
    TRANSCRIPT_TASK_REQUEST_MAX_TIMEOUT,
    TRANSCRIPT_POLL_INTERVAL,
    FETCH_TRANSCRIPT_TASK_TYPE,
    METADATA_TASK_REQUEST_DEFAULT_TIMEOUT,
    METADATA_TASK_REQUEST_MAX_TIMEOUT,
    METADATA_POLL_INTERVAL,
    FETCH_METADATA_TASK_TYPE,
)
from pydantic import ValidationError
from vidwiz.shared.logging import get_logger
from vidwiz.services.tasks_service import (
    get_transcript_task as get_transcript_task_record,
    get_metadata_task as get_metadata_task_record,
    submit_transcript_result as submit_transcript_result_record,
    submit_metadata_result as submit_metadata_result_record,
)

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

    logger.info(
        f"Transcript task poll started by user_id={getattr(request, 'user_id', None)} with timeout={timeout}s"
    )

    task = get_transcript_task_record(
        timeout,
        TRANSCRIPT_POLL_INTERVAL,
        request.user_id,
        current_app.config.get("TESTING"),
    )
    if task:
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

    task = submit_transcript_result_record(
        result_data.task_id,
        result_data.video_id,
        result_data.success,
        result_data.transcript,
        result_data.error_message,
        request.user_id,
    )
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

    logger.info(
        f"Metadata task poll started by user_id={getattr(request, 'user_id', None)} with timeout={timeout}s"
    )

    task = get_metadata_task_record(
        timeout,
        METADATA_POLL_INTERVAL,
        request.user_id,
        current_app.config.get("TESTING"),
    )
    if task:
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

    task = submit_metadata_result_record(
        result_data.task_id,
        result_data.video_id,
        result_data.success,
        result_data.metadata,
        result_data.error_message,
        request.user_id,
    )
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
