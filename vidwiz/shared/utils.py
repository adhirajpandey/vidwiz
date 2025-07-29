from flask import request, jsonify, current_app, redirect, url_for
import jwt
from functools import wraps
import requests


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


def send_request_to_ainote_lambda(
    payload: dict, lambda_url: str, auth_token: str
) -> None:
    """
    Helper function to send a request to the AI note generation Lambda function.
    """
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {auth_token}",
        }
        requests.post(lambda_url, json=payload, headers=headers)
    except requests.RequestException as e:
        print(f"Error sending request to Lambda: {e}")
        return None
