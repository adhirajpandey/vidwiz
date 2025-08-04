from flask import Blueprint, jsonify, request
from vidwiz.shared.models import Video
from vidwiz.shared.utils import jwt_required
from datetime import datetime, timedelta
import time

transcript_bp = Blueprint("transcript", __name__)


@transcript_bp.route("/transcript/task", methods=["GET"])
@jwt_required
def get_transcript_task():
    """
    Endpoint to retrieve a video task for transcript processing.
    """
    try:
        # Get timeout parameter from query string (default 30 seconds, max 60 seconds)
        timeout = min(int(request.args.get("timeout", 30)), 60)
        poll_interval = 2  # Check every 2 seconds
        start_time = time.time()

        while time.time() - start_time < timeout:

            one_minute_ago = datetime.utcnow() - timedelta(minutes=1)

            video = Video.query.filter(
                Video.created_at > one_minute_ago, Video.transcript_available.is_(False)
            ).first()

            if video:
                return jsonify(
                    {
                        "video_id": video.video_id,
                        "message": "Video task retrieved successfully",
                    }
                ), 200

            # Wait before checking again
            time.sleep(poll_interval)

        # Timeout reached, no tasks available
        return jsonify(
            {"message": "No videos available for processing", "timeout": True}
        ), 204

    except Exception as e:
        print(f"Unexpected error in get_transcript_task: {e}")
        return jsonify({"error": "Internal Server Error"}), 500
