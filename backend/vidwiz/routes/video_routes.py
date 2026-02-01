from flask import Blueprint, jsonify, request
from vidwiz.shared.schemas import VideoRead, NoteRead, VideoPatch, VideoNotesResponse
from vidwiz.shared.errors import (
    handle_validation_error,
    NotFoundError,
)
from pydantic import ValidationError
from vidwiz.shared.utils import jwt_or_lt_token_required, admin_required, require_json_body
from vidwiz.shared.logging import get_logger
from vidwiz.services.video_service import (
    fetch_video,
    fetch_ai_note_task_notes,
    update_video_summary,
)

logger = get_logger("vidwiz.routes.video_routes")

video_bp = Blueprint("video", __name__)


@video_bp.route("/videos/<video_id>", methods=["GET"])
@jwt_or_lt_token_required
def get_video(video_id):
    video = fetch_video(video_id)
    if not video:
        logger.warning(f"Video not found video_id={video_id}")
        raise NotFoundError("Video not found")
    logger.info(f"Fetched video video_id={video_id}")
    return jsonify(VideoRead.model_validate(video).model_dump()), 200


@video_bp.route("/videos/<video_id>/notes/ai-note-task", methods=["GET"])
@admin_required
def get_video_notes(video_id):
    # Check if video exists
    video, notes = fetch_ai_note_task_notes(video_id)
    if not video:
        logger.warning(f"AI-note-task: video not found video_id={video_id}")
        raise NotFoundError("Video not found")

    # Check if any notes were found
    if len(notes) == 0:
        logger.info(f"AI-note-task: no eligible notes for video_id={video_id}")
        raise NotFoundError("No notes found for users with AI notes enabled")

    # Convert notes to response format
    notes_data = [NoteRead.model_validate(note).model_dump() for note in notes]
    logger.info(
        f"AI-note-task: returning {len(notes_data)} notes for video_id={video_id}"
    )

    response_data = VideoNotesResponse(
        video_id=video_id,
        notes=notes_data,
        message="Successfully retrieved notes for AI note generation.",
    )
    return jsonify(response_data.model_dump()), 200


@video_bp.route("/videos/<video_id>", methods=["PATCH"])
@admin_required
@require_json_body
def update_video(video_id):
    """Update video fields (summary). Admin-only endpoint for Lambda."""
    # Validate input using VideoPatch schema
    try:
        patch_data = VideoPatch.model_validate(request.json_data)
    except ValidationError as e:
        logger.warning(f"Update video validation failed video_id={video_id}: {e}")
        return handle_validation_error(e)

    video = update_video_summary(video_id, patch_data.summary)
    if not video:
        logger.warning(f"Update video not found video_id={video_id}")
        raise NotFoundError("Video not found")

    if patch_data.summary is not None:
        logger.info(f"Updated video summary video_id={video_id}")
    return jsonify(VideoRead.model_validate(video).model_dump()), 200
