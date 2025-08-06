from flask import Blueprint, jsonify
from vidwiz.shared.models import Video, Note, User, db
from vidwiz.shared.schemas import VideoRead, NoteRead
from vidwiz.shared.utils import jwt_required, admin_required

video_bp = Blueprint("video", __name__)


@video_bp.route("/videos/<video_id>", methods=["GET"])
@jwt_required
def get_video(video_id):
    try:
        video = Video.query.filter_by(video_id=video_id).first()
        if not video:
            return jsonify({"error": "Video not found"}), 404
        return jsonify(VideoRead.model_validate(video).model_dump()), 200
    except Exception as e:
        print(f"Unexpected error in get_video: {e}")
        return jsonify({"error": "Internal Server Error"}), 500


@video_bp.route("/videos/<video_id>/notes/ai-note-task", methods=["GET"])
@admin_required
def get_video_notes(video_id):
    try:
        # Check if video exists
        video = Video.query.filter_by(video_id=video_id).first()
        if not video:
            return jsonify({"error": "Video not found"}), 404

        # Get notes for this video where users have AI notes enabled in their profile
        notes = (
            Note.query.join(User, Note.user_id == User.id)
            .filter(
                Note.video_id == video_id,
                User.profile_data.op("->>")("ai_notes_enabled")
                .cast(db.Boolean)
                .is_(True),
            )
            .all()
        )

        # Check if any notes were found
        if len(notes) == 0:
            return jsonify(
                {"error": "No notes found for users with AI notes enabled"}
            ), 404

        # Convert notes to response format
        notes_data = [NoteRead.model_validate(note).model_dump() for note in notes]

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
        print(f"Unexpected error in get_video_notes: {e}")
        return jsonify({"error": "Internal Server Error"}), 500
