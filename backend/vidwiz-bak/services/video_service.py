from sqlalchemy.orm import joinedload

from vidwiz.shared.models import Video, Note, User, db


def fetch_video(video_id: str):
    return Video.query.filter_by(video_id=video_id).first()


def fetch_ai_note_task_notes(video_id: str):
    """
    Return (video, notes) for AI note task processing.

    Notes include only those with empty text for users who have AI notes enabled.
    """
    video = Video.query.filter_by(video_id=video_id).first()
    if not video:
        return None, None

    bind = db.session.get_bind() or db.engine
    if bind and bind.dialect.name == "sqlite":
        notes = (
            Note.query.options(joinedload(Note.user))
            .filter(
                Note.video_id == video_id,
                db.or_(Note.text.is_(None), Note.text == ""),
            )
            .all()
        )
        notes = [
            note
            for note in notes
            if note.user
            and note.user.profile_data
            and note.user.profile_data.get("ai_notes_enabled", False)
        ]
    else:
        notes = (
            Note.query.join(User, Note.user_id == User.id)
            .filter(
                Note.video_id == video_id,
                User.profile_data.op("->>")("ai_notes_enabled")
                .cast(db.Boolean)
                .is_(True),
                db.or_(Note.text.is_(None), Note.text == ""),
            )
            .all()
        )

    return video, notes


def update_video_summary(video_id: str, summary: str | None):
    video = Video.query.filter_by(video_id=video_id).first()
    if not video:
        return None

    if summary is not None:
        video.summary = summary
        db.session.commit()
    return video
