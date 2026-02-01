from vidwiz.shared.models import Note, Video, User, db
from vidwiz.shared.tasks import create_transcript_task, create_metadata_task
from vidwiz.shared.schemas import NoteRead
from vidwiz.shared.utils import push_note_to_sqs


def ensure_video_exists(video_id: str, video_title: str | None):
    video = Video.query.filter_by(video_id=video_id).first()
    if video:
        return video, False

    if not video_title:
        return None, False

    video = Video(
        video_id=video_id,
        title=video_title,
    )
    db.session.add(video)
    db.session.commit()

    create_transcript_task(video_id)
    create_metadata_task(video_id)

    return video, True


def create_note_for_user(video_id: str, timestamp: str, text: str | None, user_id: int):
    note = Note(
        video_id=video_id,
        text=text,
        timestamp=timestamp,
        generated_by_ai=False,
        user_id=user_id,
    )
    db.session.add(note)
    db.session.commit()
    return note


def should_trigger_ai_note(note, video, user_id: int):
    if note.text:
        return False
    if not video.transcript_available:
        return False

    user = User.query.get(user_id)
    user_ai_enabled = (
        user.profile_data and user.profile_data.get("ai_notes_enabled", False)
        if user
        else False
    )
    return bool(user_ai_enabled)


def maybe_trigger_ai_note(note, video, user_id: int):
    if should_trigger_ai_note(note, video, user_id):
        push_note_to_sqs(NoteRead.model_validate(note).model_dump())
        return True
    return False


def fetch_notes_for_video(video_id: str, user_id: int):
    return Note.query.filter_by(video_id=video_id, user_id=user_id).all()


def fetch_note_for_delete(note_id: int, user_id: int):
    return Note.query.filter_by(id=note_id, user_id=user_id).first()


def delete_note(note):
    db.session.delete(note)
    db.session.commit()


def fetch_note_for_update(note_id: int, user_id: int | None, is_admin: bool):
    if is_admin:
        return Note.query.filter_by(id=note_id).first()
    return Note.query.filter_by(id=note_id, user_id=user_id).first()


def update_note(note, text: str, generated_by_ai: bool):
    note.text = text
    note.generated_by_ai = bool(generated_by_ai)
    db.session.commit()
    return note
