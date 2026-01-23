from flask import Blueprint, jsonify, request
from vidwiz.shared.utils import jwt_or_lt_token_required
from vidwiz.shared.models import Video, Note
from vidwiz.shared.errors import BadRequestError
from vidwiz.shared.logging import get_logger

core_bp = Blueprint("core", __name__)
logger = get_logger("vidwiz.routes.core_routes")


@core_bp.route("/search", methods=["GET"])
@jwt_or_lt_token_required
def get_search_results():
    query = request.args.get("query", "")  # Default to empty string for "all videos"

    # Pagination parameters
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10))
    except ValueError:
        logger.warning("Invalid pagination parameters")
        raise BadRequestError("Invalid pagination parameters")

    # Validate pagination bounds
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 10
    if per_page > 50:
        per_page = 50  # Max limit to prevent abuse

    # Only include videos that have at least one note owned by the current user
    logger.info(
        f"Searching videos for user_id={request.user_id}, query='{query}', page={page}, per_page={per_page}"
    )

    # Base query for videos with user's notes
    base_query = (
        Video.query.join(Note, Video.video_id == Note.video_id)
        .filter(Note.user_id == request.user_id)
        .group_by(Video.id)
        .order_by(Video.created_at.desc())
    )

    # Apply title filter only if query is not empty
    if query:
        base_query = base_query.filter(Video.title.ilike(f"%{query}%"))

    # Get total count for pagination metadata
    total = base_query.count()

    if total == 0:
        logger.info("Search returned 0 videos")
        return jsonify({
            "videos": [],
            "total": 0,
            "page": page,
            "per_page": per_page,
            "total_pages": 0
        }), 200

    # Calculate total pages
    total_pages = (total + per_page - 1) // per_page

    # Apply pagination
    videos = base_query.offset((page - 1) * per_page).limit(per_page).all()

    videos_data = [
        {"video_id": video.video_id, "video_title": video.title}
        for video in videos
    ]

    logger.info(f"Search returned {len(videos_data)} videos (page {page}/{total_pages}, total={total})")

    return jsonify({
        "videos": videos_data,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages
    }), 200
