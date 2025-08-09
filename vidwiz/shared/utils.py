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
    Pushes note data to an AWS SQS queue.
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
            QueueUrl=current_app.config["SQS_QUEUE_URL"],
            MessageBody=json.dumps(note_data, default=str),
        )
        logger.info(f"Note data pushed to SQS: {response}")
        return response
    except Exception as e:
        logger.error(f"Error pushing note data to SQS: {e}")
        return None


def check_required_env_vars():
    required_env_vars = [
        "DB_URL",
        "SECRET_KEY",
        "LAMBDA_URL",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_REGION",
        "SQS_QUEUE_URL",
        "S3_BUCKET_NAME",
        "ADMIN_TOKEN",
    ]
    missing = [var for var in required_env_vars if os.getenv(var) is None]
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )
