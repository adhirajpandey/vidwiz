from flask import Blueprint, jsonify, request
from vidwiz.shared.models import Video, db
from vidwiz.shared.schemas import VideoRead, VideoUpdate
from pydantic import ValidationError
from vidwiz.shared.utils import jwt_required

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


@video_bp.route("/videos/<video_id>", methods=["PATCH"])
@jwt_required
def update_video(video_id):
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        try:
            update_data = VideoUpdate(**data)
        except ValidationError as e:
            return jsonify({"error": f"Invalid data: {str(e)}"}), 400

        video = Video.query.filter_by(video_id=video_id).first()
        if not video:
            return jsonify({"error": "Video not found"}), 404

        # Update only the fields that are provided
        if update_data.title is not None:
            video.title = update_data.title
        if update_data.transcript_available is not None:
            video.transcript_available = update_data.transcript_available

        db.session.commit()
        return jsonify(VideoRead.model_validate(video).model_dump()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
