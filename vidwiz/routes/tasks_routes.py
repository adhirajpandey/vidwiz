from flask import Blueprint, jsonify, request
from vidwiz.shared.models import Task, TaskStatus, db, Video
from vidwiz.shared.utils import jwt_required, store_transcript_in_s3
from vidwiz.shared.schemas import TranscriptResult
from vidwiz.shared.config import (
    TRANSCRIPT_TASK_REQUEST_DEFAULT_TIMEOUT,
    TRANSCRIPT_TASK_REQUEST_MAX_TIMEOUT,
    TRANSCRIPT_POLL_INTERVAL,
)
from pydantic import ValidationError
from datetime import datetime
import time
import json
import boto3
import os
from sqlalchemy.orm.attributes import flag_modified


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
                # If a task is found, update its status to IN_PROGRESS and assign to worker
                task.status = TaskStatus.IN_PROGRESS
                task.started_at = datetime.now()
                task.retry_count += 1

                # Store worker information
                task.worker_details = task.worker_details or {}
                task.worker_details["worker_user_id"] = request.user_id

                db.session.commit()

                return jsonify(
                    {
                        "task_id": task.id,
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


@tasks_bp.route("/tasks/transcript", methods=["POST"])
@jwt_required
def submit_transcript_result():
    """
    Endpoint for workers to submit transcript processing results.
    """
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        try:
            result_data = TranscriptResult(**data)
        except ValidationError as e:
            return jsonify({"error": f"Invalid data: {str(e)}"}), 400

        # Find the task
        task = Task.query.get(result_data.task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404

        # Verify task belongs to the right video
        if task.task_details.get("video_id") != result_data.video_id:
            return jsonify({"error": "Task video_id mismatch"}), 400

        # Verify task is in IN_PROGRESS status
        if task.status != TaskStatus.IN_PROGRESS:
            return jsonify({"error": "Task is not in progress"}), 400

        # Verify that the request is coming from the same worker who retrieved the task
        worker_user_id = task.worker_details.get("worker_user_id", None)

        if worker_user_id != request.user_id:
            return jsonify(
                {"error": "Unauthorized: Task belongs to a different worker"}
            ), 403

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
                    print(f"Error storing transcript in S3: {s3_error}")
                    # Don't fail the task just because S3 failed

        else:
            task.status = TaskStatus.FAILED

            # Update worker_details with error information
            if task.worker_details is None:
                task.worker_details = {}

            task.worker_details["error_message"] = (
                result_data.error_message or "Unknown error occurred"
            )

            # Mark the attribute as modified to ensure SQLAlchemy detects the change

            flag_modified(task, "worker_details")

        db.session.commit()

        return jsonify(
            {
                "message": "Transcript result submitted successfully",
                "task_id": task.id,
                "status": task.status.value,
            }
        ), 200

    except Exception as e:
        db.session.rollback()
        print(f"Unexpected error in submit_transcript_result: {e}")
        return jsonify({"error": "Internal Server Error"}), 500
