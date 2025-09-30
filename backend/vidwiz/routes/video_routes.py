from flask import Blueprint, jsonify
from vidwiz.shared.models import Video, Note, User, db
from vidwiz.shared.schemas import VideoRead, NoteRead
from vidwiz.shared.utils import jwt_or_lt_token_required, admin_required
from vidwiz.shared.logging import get_logger

logger = get_logger("vidwiz.routes.video_routes")

video_bp = Blueprint("video", __name__)


@video_bp.route("/videos/<video_id>", methods=["GET"])
@jwt_or_lt_token_required
def get_video(video_id):
    try:
        video = Video.query.filter_by(video_id=video_id).first()
        if not video:
            logger.warning(f"Video not found video_id={video_id}")
            return jsonify({"error": "Video not found"}), 404
        logger.info(f"Fetched video video_id={video_id}")
        return jsonify(VideoRead.model_validate(video).model_dump()), 200
    except Exception as e:
        logger.exception(f"Unexpected error in get_video: {e}")
        return jsonify({"error": "Internal Server Error"}), 500


@video_bp.route("/videos/<video_id>/notes/ai-note-task", methods=["GET"])
@admin_required
def get_video_notes(video_id):
    try:
        # Check if video exists
        video = Video.query.filter_by(video_id=video_id).first()
        if not video:
            logger.warning(f"AI-note-task: video not found video_id={video_id}")
            return jsonify({"error": "Video not found"}), 404

        # Get notes for this video where users have AI notes enabled and the note text is empty or None
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
            logger.info(
                f"AI-note-task: no eligible notes for video_id={video_id}"
            )
            return jsonify(
                {"error": "No notes found for users with AI notes enabled"}
            ), 404

        # Convert notes to response format
        notes_data = [NoteRead.model_validate(note).model_dump() for note in notes]
        logger.info(
            f"AI-note-task: returning {len(notes_data)} notes for video_id={video_id}"
        )

        return (
            jsonify(
                {
                    "video_id": video_id,
                    "notes": notes_data,
                    "message": "Successfully retrieved notes for AI note generation.",
                }
            ),
            200,
        )
    except Exception as e:
        logger.exception(f"Unexpected error in get_video_notes: {e}")
        return jsonify({"error": "Internal Server Error"}), 500
