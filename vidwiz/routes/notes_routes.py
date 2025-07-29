from flask import Blueprint, request, jsonify
from vidwiz.shared.models import Note, Video, db
from vidwiz.shared.schemas import NoteRead, NoteCreate, NoteUpdate
from pydantic import ValidationError
from vidwiz.shared.utils import jwt_required

notes_bp = Blueprint("notes", __name__)


@notes_bp.route("/notes", methods=["POST"])
@jwt_required
def create_note():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        try:
            note_data = NoteCreate(**data)
        except ValidationError as e:
            return jsonify({"error": f"Invalid data: {str(e)}"}), 400

        # Check if video exists for this user
        video = Video.query.filter_by(
            video_id=note_data.video_id, user_id=request.user_id
        ).first()
        if not video:
            if not note_data.video_title:
                return jsonify(
                    {"error": "video_title is required when video does not exist"}
                ), 400
            video = Video(
                video_id=note_data.video_id,
                title=note_data.video_title,
                user_id=request.user_id,
            )
            db.session.add(video)
            db.session.commit()

        # Create note for this user
        note = Note(
            video_id=note_data.video_id,
            text=note_data.text,
            timestamp=note_data.timestamp,
            generated_by_ai=False,
            user_id=request.user_id,
        )
        db.session.add(note)
        db.session.commit()
        return jsonify(NoteRead.model_validate(note).model_dump()), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500


@notes_bp.route("/notes/<string:video_id>", methods=["GET"])
@jwt_required
def get_notes(video_id):
    try:
        notes = Note.query.filter_by(video_id=video_id, user_id=request.user_id).all()
        return jsonify(
            [NoteRead.model_validate(note).model_dump() for note in notes]
        ), 200
    except Exception as e:
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500


@notes_bp.route("/notes/<int:note_id>", methods=["DELETE"])
@jwt_required
def delete_note(note_id):
    try:
        note = Note.query.filter_by(id=note_id, user_id=request.user_id).first()
        if not note:
            return jsonify({"error": "Note not found"}), 404
        db.session.delete(note)
        db.session.commit()
        return jsonify({"message": "Note deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500


@notes_bp.route("/notes/<int:note_id>", methods=["PATCH"])
@jwt_required
def update_note(note_id):
    try:
        data = request.json
        if not data:
            return jsonify({"error": "Request body must be JSON"}), 400
        try:
            update_data = NoteUpdate(**data)
        except ValidationError as e:
            return jsonify({"error": f"Invalid data: {str(e)}"}), 400

        note = Note.query.filter_by(id=note_id, user_id=request.user_id).first()
        if not note:
            return jsonify({"error": "Note not found"}), 404

        note.text = update_data.text
        note.generated_by_ai = bool(update_data.generated_by_ai)
        db.session.commit()
        return jsonify(NoteRead.model_validate(note).model_dump()), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500
