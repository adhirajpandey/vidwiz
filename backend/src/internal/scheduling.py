from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.internal import constants as internal_constants
from src.internal.models import Task, TaskStatus
from src.moments.models import AiStatus, Moment
from src.videos import service as videos_service
from src.videos.models import TranscriptStatus, Video


def create_task_idempotent(db: Session, task_type: str, video_id: str) -> Task:
    """
    Create a task for the given video if it doesn't already exist in PENDING or IN_PROGRESS state.
    """
    active_tasks = (
        db.execute(
            select(Task).where(
                Task.task_type == task_type,
                Task.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS]),
            )
        )
        .scalars()
        .all()
    )

    for task in active_tasks:
        if task.task_details and task.task_details.get("video_id") == video_id:
            return task

    new_task = Task(
        task_type=task_type,
        status=TaskStatus.PENDING,
        task_details={"video_id": video_id},
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return new_task


def schedule_video_tasks(db: Session, video: Video) -> None:
    if not video.video_metadata:
        create_task_idempotent(
            db, internal_constants.FETCH_METADATA_TASK_TYPE, video.video_id
        )
    if not video.has_transcript:
        create_task_idempotent(
            db, internal_constants.FETCH_TRANSCRIPT_TASK_TYPE, video.video_id
        )
        if video.transcript_status == TranscriptStatus.UNAVAILABLE:
            # A new capture tries the transcript again, and the AI lines that gave
            # up on it wait for it again. Keeping `updated_at` keeps library order.
            videos_service.mark_transcript_pending(video)
            db.execute(
                update(Moment)
                .where(
                    Moment.video_id == video.video_id,
                    Moment.ai_status == AiStatus.NO_TRANSCRIPT,
                )
                .values(
                    ai_status=AiStatus.WAITING_TRANSCRIPT,
                    updated_at=Moment.updated_at,
                )
            )
            db.commit()


def prepare_video(db: Session, video_id: str, title: str | None = None) -> Video:
    """Upsert a video and schedule any missing transcript or metadata tasks."""
    video = videos_service.get_or_create_video(db, video_id, title)
    schedule_video_tasks(db, video)
    return video
