from flask import request, jsonify, current_app
import jwt
from functools import wraps
import requests
import threading
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
            # Admin token - set a flag to indicate admin access
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


def _send_lambda_request(
    note_id: int,
    video_id: str,
    video_title: str,
    note_timestamp: str,
    lambda_url: str,
    secret_key: str,
):
    """
    Internal function to send the actual request to Lambda.
    This runs in a separate thread.
    """
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {secret_key}",
        }
        payload = {
            "id": note_id,
            "video_id": video_id,
            "video_title": video_title,
            "note_timestamp": note_timestamp,
        }
        logger.debug(
            f"Posting AI-note request to lambda_url={lambda_url} for note_id={note_id}, video_id={video_id}"
        )
        requests.post(lambda_url, json=payload, headers=headers)
        logger.debug(f"Posted AI-note request for note_id={note_id}")
    except requests.RequestException as e:
        logger.error(f"Error sending request to Lambda: {e}")


def send_request_to_ainote_lambda(
    note_id: int, video_id: str, video_title: str, note_timestamp: str
) -> None:
    """
    Helper function to send a request to the AI note generation Lambda function.
    Uses SECRET_KEY and LAMBDA_URL from app config.
    Runs in a separate thread for fire-and-forget behavior.
    """
    try:
        # Get config values from app
        secret_key = current_app.config["SECRET_KEY"]
        lambda_url = current_app.config["LAMBDA_URL"]

        # Start the request in a separate thread (fire and forget)
        thread = threading.Thread(
            target=_send_lambda_request,
            args=(
                note_id,
                video_id,
                video_title,
                note_timestamp,
                lambda_url,
                secret_key,
            ),
            daemon=True,
        )
        thread.start()
        logger.info(
            f"Lambda request initiated in background for note_id={note_id}, video_id={video_id}, timestamp={note_timestamp}"
        )
    except Exception as e:
        logger.exception(f"Error initiating Lambda request: {e}")


def store_transcript_in_s3(video_id: str, transcript):
    """Store transcript in S3."""
    if not S3_BUCKET_NAME:
        logger.debug("Skipping S3 store: S3_BUCKET_NAME not set")
        return None
    if not transcript:
        logger.debug("Skipping S3 store: empty transcript payload")
        return None

    # Get AWS credentials from environment variables
    aws_access_key_id = current_app.config["AWS_ACCESS_KEY_ID"]
    aws_secret_access_key = current_app.config["AWS_SECRET_ACCESS_KEY"]
    aws_region = current_app.config["AWS_REGION"]

    transcript_key = f"transcripts/{video_id}.json"
    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region,
        )
        logger.debug(
            f"Uploading transcript to S3 bucket={S3_BUCKET_NAME}, key={transcript_key}, region={aws_region}"
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
