from flask import Blueprint, request, jsonify
from vidwiz.shared.logging import get_logger
from vidwiz.shared.tasks import (
    create_transcript_task,
    create_metadata_task,
    create_summary_task,
)
from vidwiz.shared.schemas import WizInitRequest, WizVideoStatusResponse
from vidwiz.shared.models import Video, Task, TaskStatus, db
from vidwiz.shared.config import (
    FETCH_TRANSCRIPT_TASK_TYPE,
    FETCH_METADATA_TASK_TYPE,
    GENERATE_SUMMARY_TASK_TYPE,
)
from pydantic import ValidationError

logger = get_logger("vidwiz.routes.wiz_routes")

wiz_bp = Blueprint("wiz", __name__)


def has_active_task(video_id: str, task_type: str) -> bool:
    """Check if there's a pending, in-progress, or completed task for the given video and task type."""
    active_statuses = [TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED]
    task = Task.query.filter(
        Task.task_type == task_type,
        Task.task_details["video_id"].as_string() == video_id,
        Task.status.in_(active_statuses),
    ).first()
    return task is not None


@wiz_bp.route("/wiz/init", methods=["POST"])
def init_wiz_session():
    """
    Initialize a wiz session for a video.
    This triggers background tasks for transcript, metadata, and summary generation.
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            logger.warning("Wiz init missing JSON body")
            return jsonify({"error": "Request body must be JSON"}), 400

        try:
            wiz_request = WizInitRequest(**data)
        except ValidationError as e:
            logger.warning(f"Wiz init validation error: {e}")
            return jsonify({"error": "Invalid request data"}), 400

        video_id = wiz_request.video_id
        logger.info(f"Initializing wiz session for video_id={video_id}")

        # Check if video exists
        video = Video.query.filter_by(video_id=video_id).first()

        if not video:
            # Create new video and queue all tasks
            logger.info(f"Creating new video for video_id={video_id}")
            video = Video(video_id=video_id)
            db.session.add(video)
            db.session.commit()

            create_transcript_task(video_id)
            create_metadata_task(video_id)
            create_summary_task(video_id)

            return (
                jsonify(
                    {
                        "message": "Video created. All tasks queued.",
                        "video_id": video_id,
                        "is_new": True,
                    }
                ),
                200,
            )

        # Video exists, check each task condition
        tasks_queued = []

        # Transcript: if not available and no active task
        if not video.transcript_available and not has_active_task(video_id, FETCH_TRANSCRIPT_TASK_TYPE):
            create_transcript_task(video_id)
            tasks_queued.append("transcript")

        # Metadata: if video_metadata is null and no active task
        if video.video_metadata is None and not has_active_task(video_id, FETCH_METADATA_TASK_TYPE):
            create_metadata_task(video_id)
            tasks_queued.append("metadata")

        # Summary: if summary is null and no active task
        if video.summary is None and not has_active_task(video_id, GENERATE_SUMMARY_TASK_TYPE):
            create_summary_task(video_id)
            tasks_queued.append("summary")

        message = f"Tasks queued: {', '.join(tasks_queued)}" if tasks_queued else "No new tasks needed."

        return (
            jsonify(
                {
                    "message": message,
                    "video_id": video_id,
                    "is_new": False,
                    "tasks_queued": tasks_queued,
                }
            ),
            200,
        )

    except Exception as e:
        logger.exception(f"Unexpected error in init_wiz_session: {e}")
        return jsonify({"error": "Internal Server Error"}), 500


@wiz_bp.route("/wiz/video/<video_id>", methods=["GET"])
def get_wiz_video_status(video_id):
    """
    Get video status for wiz workspace.
    Returns transcript_available, metadata, and summary status.
    No authentication required for wiz feature.
    """
    try:
        video = Video.query.filter_by(video_id=video_id).first()
        if not video:
            logger.warning(f"Wiz video not found video_id={video_id}")
            return jsonify({"error": "Video not found"}), 404

        response_data = WizVideoStatusResponse(
            video_id=video.video_id,
            title=video.title,
            transcript_available=video.transcript_available,
            metadata=video.video_metadata,
            summary=video.summary,
        )

        logger.info(f"Fetched wiz video status for video_id={video_id}")
        return jsonify(response_data.model_dump()), 200

    except Exception as e:
        logger.exception(f"Unexpected error in get_wiz_video_status: {e}")
        return jsonify({"error": "Internal Server Error"}), 500
