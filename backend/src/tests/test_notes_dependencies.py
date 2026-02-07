import pytest

from src.exceptions import NotFoundError
from src.notes import dependencies as notes_dependencies
from src.notes.models import Note
from src.videos.models import Video


def test_get_note_or_404(db_session):
    video = Video(video_id="note1234567A", title="Note Video")
    db_session.add(video)
    db_session.commit()

    note = Note(
        video_id=video.video_id,
        timestamp="00:01",
        text="hello",
        user_id=1,
    )
    db_session.add(note)
    db_session.commit()

    path = notes_dependencies.NoteIdPath.model_validate({"note_id": note.id})
    result = notes_dependencies.get_note_or_404(path=path, db=db_session, user_id=1)
    assert result.id == note.id

    with pytest.raises(NotFoundError):
        notes_dependencies.get_note_or_404(path=path, db=db_session, user_id=999)
