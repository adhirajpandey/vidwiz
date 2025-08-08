from vidwiz.shared.config import FETCH_TRANSCRIPT_TASK_TYPE
from vidwiz.shared.logging import get_logger

logger = get_logger("vidwiz.shared.tasks")


def create_transcript_task(
    video_id: str, task_type: str = FETCH_TRANSCRIPT_TASK_TYPE
) -> None:
    """
    Create a task for a newly created video.

    Args:
        video_id: The ID of the video
        task_type: Type of task to create (default: "transcript_processing")
    """
    try:
        from vidwiz.shared.models import Task, db

        task_details = {
            "video_id": video_id,
        }

        task = Task(task_type=task_type, task_details=task_details)

        db.session.add(task)
        db.session.commit()

        logger.info(f"Task created for video {video_id}: {task_type}")

    except Exception as e:
        logger.exception(f"Error creating task for video {video_id}: {e}")
        # Don't raise the exception to avoid disrupting video creation
        try:
            db.session.rollback()
        except Exception:
            pass
