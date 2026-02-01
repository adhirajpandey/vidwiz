from flask import Blueprint, jsonify, request
from vidwiz.shared.models import Video, Note, User, db
from sqlalchemy.orm import joinedload
from vidwiz.shared.schemas import VideoRead, NoteRead, VideoPatch, VideoNotesResponse
from vidwiz.shared.errors import (
    handle_validation_error,
    NotFoundError,
)
from pydantic import ValidationError
from vidwiz.shared.utils import jwt_or_lt_token_required, admin_required, require_json_body
from vidwiz.shared.logging import get_logger

logger = get_logger("vidwiz.routes.video_routes")

video_bp = Blueprint("video", __name__)


@video_bp.route("/videos/<video_id>", methods=["GET"])
@jwt_or_lt_token_required
def get_video(video_id):
    video = Video.query.filter_by(video_id=video_id).first()
    if not video:
        logger.warning(f"Video not found video_id={video_id}")
        raise NotFoundError("Video not found")
    logger.info(f"Fetched video video_id={video_id}")
    return jsonify(VideoRead.model_validate(video).model_dump()), 200


@video_bp.route("/videos/<video_id>/notes/ai-note-task", methods=["GET"])
@admin_required
def get_video_notes(video_id):
    # Check if video exists
    video = Video.query.filter_by(video_id=video_id).first()
    if not video:
        logger.warning(f"AI-note-task: video not found video_id={video_id}")
        raise NotFoundError("Video not found")

    # Get notes for this video where users have AI notes enabled and the note text is empty or None
    bind = db.session.get_bind() or db.engine
    if bind and bind.dialect.name == "sqlite":
        notes = (
            Note.query.options(joinedload(Note.user))
            .filter(
                Note.video_id == video_id,
                db.or_(Note.text.is_(None), Note.text == ""),
            )
            .all()
        )
        notes = [
            note
            for note in notes
            if note.user
            and note.user.profile_data
            and note.user.profile_data.get("ai_notes_enabled", False)
        ]
    else:
        notes = (
            Note.query.join(User, Note.user_id == User.id)
            .filter(
                Note.video_id == video_id,
                User.profile_data.op("->>")("ai_notes_enabled")
                .cast(db.Boolean)
                .is_(True),
                db.or_(Note.text.is_(None), Note.text == ""),
            )
            .all()
        )

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

    video = Video.query.filter_by(video_id=video_id).first()
    if not video:
        logger.warning(f"Update video not found video_id={video_id}")
        raise NotFoundError("Video not found")

    # Update summary if provided
    if patch_data.summary is not None:
        video.summary = patch_data.summary
        logger.info(f"Updated video summary video_id={video_id}")

    db.session.commit()
    return jsonify(VideoRead.model_validate(video).model_dump()), 200
