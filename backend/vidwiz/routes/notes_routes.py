from flask import Blueprint, request, jsonify
from vidwiz.shared.models import Note, Video, User, db
from vidwiz.shared.schemas import NoteRead, NoteCreate, NoteUpdate
from vidwiz.shared.errors import (
    handle_validation_error,
    NotFoundError,
    BadRequestError,
)
from pydantic import ValidationError
from vidwiz.shared.utils import (
    jwt_or_lt_token_required,
    jwt_or_admin_required,
    require_json_body,
    push_note_to_sqs,
)
from vidwiz.shared.tasks import create_transcript_task, create_metadata_task
from vidwiz.shared.logging import get_logger

notes_bp = Blueprint("notes", __name__)
logger = get_logger("vidwiz.routes.notes_routes")


@notes_bp.route("/notes", methods=["POST"])
@jwt_or_lt_token_required
@require_json_body
def create_note():
    try:
        note_data = NoteCreate.model_validate(request.json_data)
    except ValidationError as e:
        logger.warning(f"Create note validation error: {e}")
        return handle_validation_error(e)

    # Check if video exists
    video = Video.query.filter_by(video_id=note_data.video_id).first()
    if not video:
        if not note_data.video_title:
            raise BadRequestError("video_title is required when video does not exist")
        logger.info(
            f"Creating new video video_id={note_data.video_id}, title='{note_data.video_title}'"
        )
        video = Video(
            video_id=note_data.video_id,
            title=note_data.video_title,
        )
        db.session.add(video)
        db.session.commit()

        create_transcript_task(note_data.video_id)
        create_metadata_task(note_data.video_id)

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
    logger.info(
        f"Note created id={note.id} for user_id={request.user_id} video_id={note.video_id}"
    )

    # Check if we should trigger AI note generation
    user = User.query.get(request.user_id)
    user_ai_enabled = (
        user.profile_data and user.profile_data.get("ai_notes_enabled", False)
        if user
        else False
    )

    should_trigger_ai_note_gen = (
        not note_data.text  # No text provided in payload
        and video.transcript_available  # Video has transcript available
        and user_ai_enabled  # User has AI notes enabled
    )

    if should_trigger_ai_note_gen:
        logger.info(
            f"Triggering AI note generation for note_id={note.id}, video_id={note_data.video_id}"
        )
        push_note_to_sqs(NoteRead.model_validate(note).model_dump())

    return jsonify(NoteRead.model_validate(note).model_dump()), 201


@notes_bp.route("/notes/<string:video_id>", methods=["GET"])
@jwt_or_lt_token_required
def get_notes(video_id):
    notes = Note.query.filter_by(video_id=video_id, user_id=request.user_id).all()
    logger.info(
        f"Fetched {len(notes)} notes for user_id={request.user_id}, video_id={video_id}"
    )
    return jsonify(
        [NoteRead.model_validate(note).model_dump() for note in notes]
    ), 200


@notes_bp.route("/notes/<int:note_id>", methods=["DELETE"])
@jwt_or_lt_token_required
def delete_note(note_id):
    note = Note.query.filter_by(id=note_id, user_id=request.user_id).first()
    if not note:
        logger.warning(
            f"Delete note not found note_id={note_id} for user_id={request.user_id}"
        )
        raise NotFoundError("Note not found")
    db.session.delete(note)
    db.session.commit()
    logger.info(f"Deleted note_id={note_id} for user_id={request.user_id}")
    return jsonify({"message": "Note deleted successfully"}), 200


@notes_bp.route("/notes/<int:note_id>", methods=["PATCH"])
@jwt_or_admin_required
@require_json_body
def update_note(note_id):
    try:
        update_data = NoteUpdate.model_validate(request.json_data)
    except ValidationError as e:
        logger.warning(f"Update note validation error: {e}")
        return handle_validation_error(e)

    if request.is_admin:
        # Admin access - can update any note
        note = Note.query.filter_by(id=note_id).first()
    else:
        # Regular user access - can only update their own notes
        note = Note.query.filter_by(id=note_id, user_id=request.user_id).first()

    if not note:
        logger.warning(
            f"Update note not found note_id={note_id}, user_id={getattr(request, 'user_id', None)}"
        )
        raise NotFoundError("Note not found")

    note.text = update_data.text
    note.generated_by_ai = bool(update_data.generated_by_ai)
    db.session.commit()
    logger.info(
        f"Updated note_id={note.id}, generated_by_ai={note.generated_by_ai}"
    )
    return jsonify(NoteRead.model_validate(note).model_dump()), 200

