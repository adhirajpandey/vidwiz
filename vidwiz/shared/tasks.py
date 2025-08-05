def create_transcript_task(video_id: str, task_type: str = "fetch_transcript") -> None:
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

        print(f"Task created for video {video_id}: {task_type}")

    except Exception as e:
        print(f"Error creating task for video {video_id}: {e}")
        # Don't raise the exception to avoid disrupting video creation
        try:
            db.session.rollback()
        except Exception:
            pass
