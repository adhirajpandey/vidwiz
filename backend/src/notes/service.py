from sqlalchemy import select
from sqlalchemy.orm import Session

from src.notes.models import Note
from src.videos.models import Video
from src.videos import service as videos_service


def get_or_create_video(
    db: Session, video_id: str, video_title: str | None
) -> tuple[Video, bool]:
    video = videos_service.get_video_by_id(db, video_id)
    if video:
        if video_title and not video.title:
            video.title = video_title
            db.commit()
            db.refresh(video)
        return video, False

    video = Video(video_id=video_id, title=video_title)
    db.add(video)
    db.commit()
    db.refresh(video)
    return video, True


def create_note_for_user(
    db: Session, video_id: str, timestamp: str, text: str | None, user_id: int
) -> Note:
    note = Note(
        video_id=video_id,
        timestamp=timestamp,
        text=text,
        generated_by_ai=False,
        user_id=user_id,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def list_notes_for_video(db: Session, user_id: int, video_id: str) -> list[Note]:
    query = (
        select(Note)
        .where(Note.user_id == user_id, Note.video_id == video_id)
        .order_by(Note.created_at.asc(), Note.id.asc())
    )
    return db.execute(query).scalars().all()


def get_note_for_user(db: Session, user_id: int, note_id: int) -> Note | None:
    query = select(Note).where(Note.user_id == user_id, Note.id == note_id)
    return db.execute(query).scalar_one_or_none()


def get_note_by_id(db: Session, note_id: int) -> Note | None:
    return db.get(Note, note_id)


def update_note(
    db: Session,
    note: Note,
    text: str | None,
    generated_by_ai: bool | None,
) -> Note:
    if text is not None:
        note.text = text
    if generated_by_ai is not None:
        note.generated_by_ai = bool(generated_by_ai)
    db.commit()
    db.refresh(note)
    return note


def delete_note(db: Session, note: Note) -> None:
    db.delete(note)
    db.commit()
