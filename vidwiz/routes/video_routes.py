from flask import Blueprint, jsonify, request
from vidwiz.shared.models import Video
from vidwiz.shared.schemas import VideoRead
from vidwiz.shared.utils import jwt_required

video_bp = Blueprint("video", __name__)


@video_bp.route("/videos/<video_id>", methods=["GET"])
@jwt_required
def get_video(video_id):
    try:
        video = Video.query.filter_by(
            video_id=video_id, user_id=request.user_id
        ).first()
        if not video:
            return jsonify({"error": "Video not found"}), 404
        return jsonify(VideoRead.model_validate(video).model_dump()), 200
    except Exception as e:
        print(f"Unexpected error in get_video: {e}")
        return jsonify({"error": "Internal Server Error"}), 500
