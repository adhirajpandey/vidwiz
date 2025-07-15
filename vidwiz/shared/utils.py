from flask import request, jsonify, current_app
from functools import wraps
import requests


def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get("Authorization")
        if token is None or token != f"Bearer {current_app.config['AUTH_TOKEN']}":
            return jsonify({"error": "Unauthorized"}), 401
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
