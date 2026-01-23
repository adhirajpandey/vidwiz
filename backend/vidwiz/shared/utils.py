from flask import request, jsonify, current_app
import jwt
from functools import wraps
import os
import boto3
from vidwiz.shared.config import S3_BUCKET_NAME
import json
from vidwiz.shared.logging import get_logger

logger = get_logger("vidwiz.shared.utils")


def jwt_or_lt_token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from vidwiz.shared.models import User  # Import here to avoid circular imports

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.warning("Auth failed: missing/invalid Authorization header")
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth_header.split(" ", 1)[1]

        # First try to decode as JWT
        try:
            payload = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            request.user_id = payload["user_id"]
            logger.debug(f"JWT auth succeeded for user_id={request.user_id}")
            return f(*args, **kwargs)
        except Exception:
            # JWT decoding failed, try to check if it's a long term token
            logger.debug("JWT decode failed; attempting long-term token auth")
            pass

        # Check if token matches any user's long_term_token
        try:
            user = User.query.filter_by(long_term_token=token).first()
            if user:
                request.user_id = user.id
                logger.debug(f"Long-term token auth succeeded for user_id={user.id}")
                return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error during long-term token lookup: {e}")

        logger.warning("Auth failed: invalid/expired token or not a long-term token")
        return jsonify(
            {"error": "Invalid or expired token or not a long term token"}
        ), 401

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.warning("Admin auth failed: missing/invalid Authorization header")
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth_header.split(" ", 1)[1]

        # Check if token matches ADMIN_TOKEN
        admin_token = os.getenv("ADMIN_TOKEN")
        if not admin_token:
            logger.error("Admin access attempted but ADMIN_TOKEN not configured")
            return jsonify({"error": "Admin access not configured"}), 500

        if token != admin_token:
            logger.warning("Admin auth failed: invalid admin token")
            return jsonify({"error": "Invalid admin token"}), 403

        logger.debug("Admin auth succeeded")
        return f(*args, **kwargs)

    return decorated_function


def jwt_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.warning(
                "Auth (admin/JWT) failed: missing/invalid Authorization header"
            )
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth_header.split(" ", 1)[1]

        # First check if it's an admin token
        admin_token = os.getenv("ADMIN_TOKEN")
        if admin_token and token == admin_token:
            request.is_admin = True
            request.user_id = None  # Admin doesn't have a specific user_id
            logger.debug("Admin token accepted for route access")
            return f(*args, **kwargs)

        # If not admin token, try to decode as JWT
        try:
            payload = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            request.user_id = payload["user_id"]
            request.is_admin = False
            logger.debug(
                f"JWT auth (non-admin) succeeded for user_id={request.user_id}"
            )
        except Exception:
            logger.warning("Auth (admin/JWT) failed: invalid or expired token")
            return jsonify({"error": "Invalid or expired token"}), 401

        return f(*args, **kwargs)

    return decorated_function


def require_json_body(f):
    """
    Decorator to ensure request has a valid JSON body.
    
    Raises BadRequestError if:
    - Content-Type is not application/json
    - Request body is empty or not valid JSON
    
    Sets request.json_data with the parsed JSON for use in the route.
    
    Usage:
        @app.route('/api/resource', methods=['POST'])
        @jwt_or_lt_token_required
        @require_json_body
        def create_resource():
            data = request.json_data  # Already validated
            ...
    """
    from vidwiz.shared.errors import BadRequestError
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        data = request.get_json(silent=True)
        if not data:
            logger.warning(f"Missing JSON body for {request.endpoint}")
            raise BadRequestError("Request body must be JSON")
        
        # Store parsed JSON for use in route
        request.json_data = data
        return f(*args, **kwargs)
    
    return decorated_function


def get_transcript_from_s3(video_id: str) -> list | None:
    """
    Get transcript from S3 cache.

    Args:
        video_id: Unique identifier for the video

    Returns:
        List of transcript segments or None if not found
    """
    if not S3_BUCKET_NAME:
        logger.debug("Skipping S3 fetch: S3_BUCKET_NAME not set")
        return None

    transcript_key = f"transcripts/{video_id}.json"
    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=current_app.config["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=current_app.config["AWS_SECRET_ACCESS_KEY"],
            region_name=current_app.config["AWS_REGION"],
        )
        logger.info(
            "Fetching transcript from S3",
            extra={
                "bucket": S3_BUCKET_NAME,
                "key": transcript_key,
                "video_id": video_id,
            },
        )

        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=transcript_key)
        transcript_data = json.loads(response["Body"].read().decode("utf-8"))

        logger.info(
            "Successfully loaded transcript from S3",
            extra={"video_id": video_id, "segment_count": len(transcript_data)},
        )
        return transcript_data

    except Exception as e:
        logger.warning(
            "Transcript not found in S3", extra={"video_id": video_id, "error": str(e)}
        )
        return None


def store_transcript_in_s3(video_id: str, transcript):
    """Store transcript in S3."""
    if not S3_BUCKET_NAME:
        logger.debug("Skipping S3 store: S3_BUCKET_NAME not set")
        return None
    if not transcript:
        logger.debug("Skipping S3 store: empty transcript payload")
        return None

    # Get AWS credentials from environment variables

    transcript_key = f"transcripts/{video_id}.json"
    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=current_app.config["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=current_app.config["AWS_SECRET_ACCESS_KEY"],
            region_name=current_app.config["AWS_REGION"],
        )
        logger.debug(
            f"Uploading transcript to S3 bucket={S3_BUCKET_NAME}, key={transcript_key}, region={current_app.config['AWS_REGION']}"
        )
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=transcript_key,
            Body=json.dumps(transcript),
            ContentType="application/json",
        )
        logger.info(
            f"Successfully stored transcript in S3: s3://{S3_BUCKET_NAME}/{transcript_key}"
        )
    except Exception as e:
        logger.error(f"Error storing transcript in S3: {e}")
        return None



def push_note_to_sqs(note_data):
    """
    Alias for push_note_to_ai_note_sqs to maintain backward compatibility.
    """
    return push_note_to_ai_note_sqs(note_data)


def push_note_to_ai_note_sqs(note_data):
    """
    Pushes note data to the AI Note generation SQS queue.
    Args:
        note_data (dict): The note data to send.
    Returns:
        dict: Response from SQS send_message, or None if error.
    """

    try:
        sqs = boto3.client(
            "sqs",
            aws_access_key_id=current_app.config["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=current_app.config["AWS_SECRET_ACCESS_KEY"],
            region_name=current_app.config["AWS_REGION"],
        )
        response = sqs.send_message(
            QueueUrl=current_app.config["SQS_AI_NOTE_QUEUE_URL"],
            MessageBody=json.dumps(note_data, default=str),
        )
        logger.info(f"Note data pushed to AI Note SQS: {response}")
        return response
    except Exception as e:
        logger.error(f"Error pushing note data to AI Note SQS: {e}")
        return None


def push_video_to_summary_sqs(video_id: str):
    """
    Pushes video_id to the Summary generation SQS queue.
    Args:
        video_id (str): The video ID to process for summary generation.
    Returns:
        dict: Response from SQS send_message, or None if error.
    """

    try:
        sqs = boto3.client(
            "sqs",
            aws_access_key_id=current_app.config["AWS_ACCESS_KEY_ID"],
            aws_secret_access_key=current_app.config["AWS_SECRET_ACCESS_KEY"],
            region_name=current_app.config["AWS_REGION"],
        )
        message_data = {"video_id": video_id}
        response = sqs.send_message(
            QueueUrl=current_app.config["SQS_SUMMARY_QUEUE_URL"],
            MessageBody=json.dumps(message_data),
        )
        logger.info(f"Video ID pushed to Summary SQS: {response}")
        return response
    except Exception as e:
        logger.error(f"Error pushing video ID to Summary SQS: {e}")
        return None


def check_required_env_vars():
    required_env_vars = [
        "DB_URL",
        "SECRET_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_REGION",
        "SQS_AI_NOTE_QUEUE_URL",
        "SQS_SUMMARY_QUEUE_URL",
        "S3_BUCKET_NAME",
        "ADMIN_TOKEN",
    ]
    missing = [var for var in required_env_vars if os.getenv(var) is None]
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )
