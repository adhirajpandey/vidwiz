from flask import Blueprint, jsonify, request
from vidwiz.shared.models import Task, TaskStatus, db
from vidwiz.shared.utils import jwt_required
from vidwiz.shared.config import (
    TRANSCRIPT_TASK_REQUEST_DEFAULT_TIMEOUT,
    TRANSCRIPT_TASK_REQUEST_MAX_TIMEOUT,
    TRANSCRIPT_POLL_INTERVAL,
)
from datetime import datetime
import time

tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.route("/tasks/transcript", methods=["GET"])
@jwt_required
def get_transcript_task():
    """
    Endpoint to retrieve a transcript task for processing from the task table.
    """
    try:
        timeout = min(
            int(request.args.get("timeout", TRANSCRIPT_TASK_REQUEST_DEFAULT_TIMEOUT)),
            TRANSCRIPT_TASK_REQUEST_MAX_TIMEOUT,
        )

        start_time = time.time()

        while time.time() - start_time < timeout:
            # Look for pending transcript tasks or stale in-progress tasks
            task = (
                Task.query.filter(Task.task_type == "fetch_transcript")
                .filter((Task.status == TaskStatus.PENDING))
                .first()
            )

            if task:
                # If a task is found, update its status to IN_PROGRESS
                task.status = TaskStatus.IN_PROGRESS
                task.started_at = datetime.now()
                task.retry_count += 1
                db.session.commit()

                return jsonify(
                    {
                        "task_type": task.task_type,
                        "task_details": task.task_details,
                        "retry_count": task.retry_count,
                        "message": "Transcript task retrieved successfully",
                    }
                ), 200

            time.sleep(TRANSCRIPT_POLL_INTERVAL)

        return jsonify(
            {"message": "No transcript tasks available for processing", "timeout": True}
        ), 204

    except Exception as e:
        print(f"Unexpected error in get_transcript_task: {e}")
        return jsonify({"error": "Internal Server Error"}), 500
