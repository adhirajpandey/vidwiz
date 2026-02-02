from flask import Blueprint, request, jsonify
from vidwiz.shared.schemas import NoteRead, NoteCreate, NoteUpdate, MessageResponse
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
)
from vidwiz.shared.logging import get_logger
from vidwiz.services.notes_service import (
    ensure_video_exists,
    create_note_for_user,
    maybe_trigger_ai_note,
    fetch_notes_for_video,
    fetch_note_for_delete,
    delete_note as delete_note_record,
    fetch_note_for_update,
    update_note as update_note_record,
)

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
    video, created = ensure_video_exists(note_data.video_id, note_data.video_title)
    if not video:
        raise BadRequestError("video_title is required when video does not exist")
    if created:
        logger.info(
            f"Creating new video video_id={note_data.video_id}, title='{note_data.video_title}'"
        )

    # Create note for this user
    note = create_note_for_user(
        note_data.video_id,
        note_data.timestamp,
        note_data.text,
        request.user_id,
    )
    logger.info(
        f"Note created id={note.id} for user_id={request.user_id} video_id={note.video_id}"
    )
    if maybe_trigger_ai_note(note, video, request.user_id):
        logger.info(
            f"Triggering AI note generation for note_id={note.id}, video_id={note_data.video_id}"
        )

    return jsonify(NoteRead.model_validate(note).model_dump()), 201


@notes_bp.route("/notes/<string:video_id>", methods=["GET"])
@jwt_or_lt_token_required
def get_notes(video_id):
    notes = fetch_notes_for_video(video_id, request.user_id)
    logger.info(
        f"Fetched {len(notes)} notes for user_id={request.user_id}, video_id={video_id}"
    )
    return jsonify(
        [NoteRead.model_validate(note).model_dump() for note in notes]
    ), 200


@notes_bp.route("/notes/<int:note_id>", methods=["DELETE"])
@jwt_or_lt_token_required
def delete_note(note_id):
    note = fetch_note_for_delete(note_id, request.user_id)
    if not note:
        logger.warning(
            f"Delete note not found note_id={note_id} for user_id={request.user_id}"
        )
        raise NotFoundError("Note not found")
    delete_note_record(note)
    logger.info(f"Deleted note_id={note_id} for user_id={request.user_id}")
    return jsonify(MessageResponse(message="Note deleted successfully").model_dump()), 200


@notes_bp.route("/notes/<int:note_id>", methods=["PATCH"])
@jwt_or_admin_required
@require_json_body
def update_note(note_id):
    try:
        update_data = NoteUpdate.model_validate(request.json_data)
    except ValidationError as e:
        logger.warning(f"Update note validation error: {e}")
        return handle_validation_error(e)

    note = fetch_note_for_update(
        note_id, getattr(request, "user_id", None), request.is_admin
    )

    if not note:
        logger.warning(
            f"Update note not found note_id={note_id}, user_id={getattr(request, 'user_id', None)}"
        )
        raise NotFoundError("Note not found")

    note = update_note_record(note, update_data.text, update_data.generated_by_ai)
    logger.info(
        f"Updated note_id={note.id}, generated_by_ai={note.generated_by_ai}"
    )
    return jsonify(NoteRead.model_validate(note).model_dump()), 200
