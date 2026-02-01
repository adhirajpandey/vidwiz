from flask import Blueprint, jsonify, request
from vidwiz.shared.utils import jwt_or_lt_token_required
from vidwiz.shared.errors import BadRequestError
from vidwiz.shared.logging import get_logger
from vidwiz.services.core_service import search_videos_for_user

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

    response = search_videos_for_user(request.user_id, query, page, per_page)

    logger.info(
        "Search returned %s videos (page %s/%s, total=%s)",
        len(response.videos),
        response.page,
        response.total_pages,
        response.total,
    )

    return jsonify(response.model_dump()), 200
