from flask import Blueprint, jsonify, request
from vidwiz.shared.utils import jwt_or_lt_token_required
from vidwiz.shared.models import Video, Note
from vidwiz.shared.logging import get_logger

core_bp = Blueprint("core", __name__)
logger = get_logger("vidwiz.routes.core_routes")


@core_bp.route("/search", methods=["GET"])
@jwt_or_lt_token_required
def get_search_results():
    query = request.args.get("query", None)
    if query is None:
        logger.warning("Search request missing 'query' parameter")
        return jsonify({"error": "Query parameter is required"}), 400
    # Only include videos that have at least one note owned by the current user
    logger.info(f"Searching videos for user_id={request.user_id}, query='{query}'")
    videos = (
        Video.query.filter(Video.title.ilike(f"%{query}%"))
        .join(Note, Video.video_id == Note.video_id)
        .filter(Note.user_id == request.user_id)
        .group_by(Video.id)
        .order_by(Video.created_at.desc())
        .all()
    )
    if not videos:
        logger.info("Search returned 0 videos")
        return jsonify({"error": "No videos found matching the query"}), 404
    all_videos = [
        {"video_id": video.video_id, "video_title": video.title} for video in videos
    ]
    logger.info(f"Search returned {len(all_videos)} videos")
    return jsonify(all_videos), 200
