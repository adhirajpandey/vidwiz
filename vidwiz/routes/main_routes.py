from flask import Blueprint, current_app, request, jsonify, render_template
from vidwiz.models import Note, db
from vidwiz.schemas import NoteCreate, NoteRead, NoteUpdate
from pydantic import ValidationError
from functools import wraps
import requests
import threading

main_bp = Blueprint("main", __name__)


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


def token_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import current_app

        token = request.headers.get("Authorization")
        if token is None or token != f"Bearer {current_app.config['AUTH_TOKEN']}":
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)

    return decorated_function


@main_bp.route("/", methods=["GET"])
def index():
    return jsonify({"message": "Welcome to the VidWiz APP!"})


@main_bp.route("/notes", methods=["POST"])
@token_required
def create_note():
    try:
        data = request.json
        if data is None or data == {}:
            return jsonify({"error": "Request body must be JSON"}), 400
        try:
            note_data = NoteCreate(**data)
        except ValidationError as e:
            print(f"Validation error in create_note: {e}")
            return jsonify({"error": f"Invalid data: {str(e)}"}), 400

        new_note = Note(**note_data.model_dump())
        db.session.add(new_note)
        db.session.commit()

        # if created note does not have note, gen note using AI if AI_NOTE_TOGGLE is enabled
        if not new_note.note and current_app.config.get("AI_NOTE_TOGGLE", False):
            payload = {
                "id": new_note.id,
                "video_id": new_note.video_id,
                "video_title": new_note.video_title,
                "note_timestamp": new_note.note_timestamp,
            }

            # Pass config values to avoid application context issues - fire-and-forget
            lambda_url = current_app.config["LAMBDA_URL"]
            auth_token = current_app.config["AUTH_TOKEN"]
            thread = threading.Thread(
                target=send_request_to_ainote_lambda,
                args=(payload, lambda_url, auth_token),
            )
            thread.daemon = True
            thread.start()

        return jsonify(NoteRead.model_validate(new_note).model_dump()), 201
    except Exception as e:
        print(f"Unexpected error in create_note: {e}")
        db.session.rollback()
        return jsonify({"error": "Internal Server Error"}), 500


@main_bp.route("/video-notes/<video_id>", methods=["GET"])
@token_required
def get_notes_by_video(video_id):
    try:
        notes = Note.query.filter_by(video_id=video_id).all()
        if not notes:
            return jsonify({"error": "No notes found for the given video_id"}), 404
        return jsonify(
            [NoteRead.model_validate(note).model_dump() for note in notes]
        ), 200
    except Exception as e:
        print(f"Unexpected error in get_notes_by_video: {e}")
        return jsonify({"error": "Internal Server Error"}), 500


@main_bp.route("/search", methods=["GET"])
@token_required
def get_search_results():
    try:
        query = request.args.get("query", None)
        if query is None:
            return jsonify({"error": "Query parameter is required"}), 400

        result = (
            db.session.query(Note.video_id, Note.video_title, Note.created_at)
            .filter(Note.video_title.ilike(f"%{query}%"))
            .distinct(Note.video_id)
            .all()
        )

        if not result:
            return jsonify({"error": "No videos found matching the query"}), 404

        sorted_result = sorted(result, key=lambda x: x.created_at, reverse=True)
        all_videos = [
            {"video_id": video.video_id, "video_title": video.video_title}
            for video in sorted_result
        ]
        return jsonify(all_videos), 200
    except Exception as e:
        print(f"Unexpected error in get_search_results: {e}")
        return jsonify({"error": "Internal Server Error"}), 500


@main_bp.route("/notes/<int:note_id>", methods=["PATCH"])
@token_required
def update_note(note_id):
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400

        try:
            update_data = NoteUpdate(**data)
        except ValidationError as e:
            print(f"Validation error in update_note: {e}")
            return jsonify({"error": f"Invalid data: {str(e)}"}), 400

        note = Note.query.get(note_id)
        if not note:
            return jsonify({"error": "Note not found"}), 404

        # Update note fields if provided
        if update_data.note is not None:
            note.note = update_data.note
        if update_data.ai_note is not None:
            note.ai_note = update_data.ai_note

        db.session.commit()
        return jsonify(NoteRead.model_validate(note).model_dump()), 200
    except Exception as e:
        print(f"Unexpected error in update_note: {e}")
        db.session.rollback()
        return jsonify({"error": "Internal Server Error"}), 500


@main_bp.route("/notes/<int:note_id>", methods=["DELETE"])
@token_required
def delete_note(note_id):
    try:
        note = Note.query.get(note_id)
        if not note:
            return jsonify({"error": "Note not found"}), 404

        db.session.delete(note)
        db.session.commit()
        return jsonify({"message": "Note deleted successfully"}), 200
    except Exception as e:
        print(f"Unexpected error in delete_note: {e}")
        db.session.rollback()
        return jsonify({"error": "Internal Server Error"}), 500


@main_bp.route("/dashboard", methods=["GET"])
def get_dashboard_page():
    return render_template("dashboard.html")


@main_bp.route("/dashboard/<video_id>", methods=["GET"])
def get_video_page(video_id):
    return render_template("video.html")