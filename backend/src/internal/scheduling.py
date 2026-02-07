from sqlalchemy import select
from sqlalchemy.orm import Session

from src.internal import constants as internal_constants
from src.internal.models import Task, TaskStatus
from src.videos.models import Video


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
    if not video.transcript_available:
        create_task_idempotent(
            db, internal_constants.FETCH_TRANSCRIPT_TASK_TYPE, video.video_id
        )
