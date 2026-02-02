from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.auth.dependencies import (
    get_current_user_id,
    get_current_user_id_or_long_term,
)
from src.database import get_db
from src.exceptions import BadRequestError
from src.notes import service as notes_service
from src.notes.dependencies import get_note_or_404
from src.notes.schemas import MessageResponse, NoteCreate, NoteRead, NoteUpdate
from src.videos.schemas import VideoIdPath


router = APIRouter(prefix="/api/v2", tags=["Notes"])


@router.get(
    "/videos/{video_id}/notes",
    response_model=list[NoteRead],
    status_code=status.HTTP_200_OK,
    description="List notes for a video.",
)
def list_notes(
    path: VideoIdPath = Depends(),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[NoteRead]:
    notes = notes_service.list_notes_for_video(db, user_id, path.video_id)
    return [NoteRead.model_validate(note) for note in notes]


@router.post(
    "/videos/{video_id}/notes",
    response_model=NoteRead,
    status_code=status.HTTP_201_CREATED,
    description="Create a note; implicitly creates the video if missing.",
)
def create_note(
    payload: NoteCreate,
    path: VideoIdPath = Depends(),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id_or_long_term),
) -> NoteRead:
    notes_service.get_or_create_video(db, path.video_id, payload.video_title)
    note = notes_service.create_note_for_user(
        db,
        path.video_id,
        payload.timestamp,
        payload.text,
        user_id,
    )
    return NoteRead.model_validate(note)


@router.patch(
    "/notes/{note_id}",
    response_model=NoteRead,
    status_code=status.HTTP_200_OK,
    description="Update note text/flags.",
)
def update_note(
    payload: NoteUpdate,
    db: Session = Depends(get_db),
    note=Depends(get_note_or_404),
) -> NoteRead:
    if payload.text is None and payload.generated_by_ai is None:
        raise BadRequestError("No fields provided for update")

    updated = notes_service.update_note(
        db,
        note,
        payload.text,
        payload.generated_by_ai,
    )
    return NoteRead.model_validate(updated)


@router.delete(
    "/notes/{note_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    description="Delete a note.",
)
def delete_note(
    db: Session = Depends(get_db),
    note=Depends(get_note_or_404),
) -> MessageResponse:
    notes_service.delete_note(db, note)
    return MessageResponse(message="Note deleted successfully")
