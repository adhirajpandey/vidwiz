from flask import Blueprint, jsonify, request
from vidwiz.shared.models import Video, db
from vidwiz.shared.schemas import VideoRead, VideoUpdate, VideoCreate
from pydantic import ValidationError
from vidwiz.shared.utils import admin_required
from vidwiz.shared.tasks import create_transcript_task

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/videos", methods=["POST"])
@admin_required
def create_video():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        try:
            video_data = VideoCreate(**data)
        except ValidationError as e:
            return jsonify({"error": f"Invalid data: {str(e)}"}), 400

        # Check if video already exists
        existing_video = Video.query.filter_by(video_id=video_data.video_id).first()
        if existing_video:
            return jsonify({"error": "Video with this ID already exists"}), 409

        # Create new video
        video = Video(
            video_id=video_data.video_id,
            title=video_data.title,
            transcript_available=video_data.transcript_available,
        )

        db.session.add(video)
        db.session.commit()

        # Create task for the new video
        create_transcript_task(video_data.video_id)

        return jsonify(VideoRead.model_validate(video).model_dump()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500


@admin_bp.route("/videos/<video_id>", methods=["PATCH"])
@admin_required
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


@admin_bp.route("/videos/<video_id>", methods=["DELETE"])
@admin_required
def delete_video(video_id):
    try:
        video = Video.query.filter_by(video_id=video_id).first()
        if not video:
            return jsonify({"error": "Video not found"}), 404

        db.session.delete(video)
        db.session.commit()
        return jsonify({"message": "Video deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500


@admin_bp.route("/videos", methods=["GET"])
@admin_required
def list_all_videos():
    try:
        videos = Video.query.order_by(Video.created_at.desc()).all()
        return jsonify(
            [VideoRead.model_validate(video).model_dump() for video in videos]
        ), 200
    except Exception as e:
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
