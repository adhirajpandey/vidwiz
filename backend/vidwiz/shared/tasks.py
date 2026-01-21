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


def create_metadata_task(
    video_id: str, task_type: str = None
) -> None:
    """
    Create a metadata fetch task for a newly created video.

    Args:
        video_id: The ID of the video
        task_type: Type of task to create (default: "fetch_metadata")
    """
    from vidwiz.shared.config import FETCH_METADATA_TASK_TYPE

    if task_type is None:
        task_type = FETCH_METADATA_TASK_TYPE

    try:
        from vidwiz.shared.models import Task, db

        task_details = {
            "video_id": video_id,
        }

        task = Task(task_type=task_type, task_details=task_details)

        db.session.add(task)
        db.session.commit()

        logger.info(f"Metadata task created for video {video_id}: {task_type}")

    except Exception as e:
        logger.exception(f"Error creating metadata task for video {video_id}: {e}")
        # Don't raise the exception to avoid disrupting video creation
        try:
            db.session.rollback()
        except Exception:
            pass


def create_summary_task(
    video_id: str, task_type: str = None
) -> None:
    """
    Create a summary generation task for a newly created video.

    Args:
        video_id: The ID of the video
        task_type: Type of task to create (default: "generate_summary")
    """
    from vidwiz.shared.config import GENERATE_SUMMARY_TASK_TYPE

    if task_type is None:
        task_type = GENERATE_SUMMARY_TASK_TYPE

    try:
        from vidwiz.shared.models import Task, db

        task_details = {
            "video_id": video_id,
        }

        task = Task(task_type=task_type, task_details=task_details)

        db.session.add(task)
        db.session.commit()

        logger.info(f"Summary task created for video {video_id}: {task_type}")

    except Exception as e:
        logger.exception(f"Error creating summary task for video {video_id}: {e}")
        # Don't raise the exception to avoid disrupting video creation
        try:
            db.session.rollback()
        except Exception:
            pass
