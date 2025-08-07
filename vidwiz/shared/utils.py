from flask import request, jsonify, current_app
import jwt
from functools import wraps
import requests
import threading
import os
import boto3
from vidwiz.shared.config import S3_BUCKET_NAME
import json


def jwt_or_lt_token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from vidwiz.shared.models import User  # Import here to avoid circular imports

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth_header.split(" ", 1)[1]

        # First try to decode as JWT
        try:
            payload = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            request.user_id = payload["user_id"]
            return f(*args, **kwargs)
        except Exception:
            # JWT decoding failed, try to check if it's a long term token
            pass

        # Check if token matches any user's long_term_token
        try:
            user = User.query.filter_by(long_term_token=token).first()
            if user:
                request.user_id = user.id
                return f(*args, **kwargs)
        except Exception:
            pass

        return jsonify(
            {"error": "Invalid or expired token or not a long term token"}
        ), 401

    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth_header.split(" ", 1)[1]

        # Check if token matches ADMIN_TOKEN
        admin_token = os.getenv("ADMIN_TOKEN")
        if not admin_token:
            return jsonify({"error": "Admin access not configured"}), 500

        if token != admin_token:
            return jsonify({"error": "Invalid admin token"}), 403

        return f(*args, **kwargs)

    return decorated_function


def jwt_or_admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth_header.split(" ", 1)[1]

        # First check if it's an admin token
        admin_token = os.getenv("ADMIN_TOKEN")
        if admin_token and token == admin_token:
            # Admin token - set a flag to indicate admin access
            request.is_admin = True
            request.user_id = None  # Admin doesn't have a specific user_id
            return f(*args, **kwargs)

        # If not admin token, try to decode as JWT
        try:
            payload = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            request.user_id = payload["user_id"]
            request.is_admin = False
        except Exception:
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
        requests.post(lambda_url, json=payload, headers=headers)
    except requests.RequestException as e:
        print(f"Error sending request to Lambda: {e}")


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
        print(f"Lambda request initiated in background for note {note_id}")
    except Exception as e:
        print(f"Error initiating Lambda request: {e}")


def store_transcript_in_s3(video_id: str, transcript):
    """Store transcript in S3."""
    if not S3_BUCKET_NAME or not transcript:
        return None

    # Get AWS credentials from environment variables
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION", "ap-south-1")

    if not aws_access_key_id or not aws_secret_access_key:
        print("Error: AWS credentials not found in environment variables")
        return None

    transcript_key = f"transcripts/{video_id}.json"
    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region,
        )
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=transcript_key,
            Body=json.dumps(transcript),
            ContentType="application/json",
        )
        print(
            f"Successfully stored transcript in S3: s3://{S3_BUCKET_NAME}/{transcript_key}"
        )
    except Exception as e:
        print(f"Error storing transcript in S3: {e}")
        return None
