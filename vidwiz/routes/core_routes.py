from flask import Blueprint, jsonify, render_template, request
from vidwiz.shared.utils import token_required
from vidwiz.shared.models import Video

core_bp = Blueprint("core", __name__)


@core_bp.route("/", methods=["GET"])
def index():
    return jsonify({"message": "Welcome to the VidWiz APP!"})


@core_bp.route("/dashboard", methods=["GET"])
def get_dashboard_page():
    return render_template("dashboard.html")


@core_bp.route("/dashboard/<video_id>", methods=["GET"])
def get_video_page(video_id):
    return render_template("video.html")


@core_bp.route("/search", methods=["GET"])
@token_required
def get_search_results():
    query = request.args.get("query", None)
    if query is None:
        return jsonify({"error": "Query parameter is required"}), 400
    videos = (
        Video.query.filter(Video.title.ilike(f"%{query}%"))
        .order_by(Video.created_at.desc())
        .all()
    )
    if not videos:
        return jsonify({"error": "No videos found matching the query"}), 404
    all_videos = [
        {"video_id": video.video_id, "video_title": video.title} for video in videos
    ]
    return jsonify(all_videos), 200
