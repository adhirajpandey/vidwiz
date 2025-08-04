from flask import request, jsonify, current_app
import jwt
from functools import wraps
import requests
import threading
import os


def jwt_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401
        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            request.user_id = payload["user_id"]
        except Exception:
            return jsonify({"error": "Invalid or expired token"}), 401
        return f(*args, **kwargs)

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
