from fastapi import Depends
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user_id
from src.database import get_db
from src.exceptions import NotFoundError
from src.notes import service as notes_service
from src.notes.schemas import NoteIdPath


def get_note_or_404(
    path: NoteIdPath = Depends(),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    note = notes_service.get_note_for_user(db, user_id, path.note_id)
    if not note:
        raise NotFoundError("Note not found")
    return note
