import pytest

from src.config import settings
from src.internal import constants as internal_constants
from src.internal.models import Task, TaskStatus
from src.auth.models import User
from src.notes.models import Note
from src.videos.models import Video


def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.admin_token}"}


@pytest.mark.asyncio
async def test_internal_task_poll_transcript_success(client, db_session):
    task = Task(
        task_type=internal_constants.FETCH_TRANSCRIPT_TASK_TYPE,
        status=TaskStatus.PENDING,
        task_details={"video_id": "test_video"},
        retry_count=0,
    )
    db_session.add(task)
    db_session.commit()

    response = await client.get(
        "/api/v2/internal/tasks?type=transcript&timeout=1",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["task_id"] == task.id
    assert payload["task_type"] == internal_constants.FETCH_TRANSCRIPT_TASK_TYPE
    assert payload["task_details"]["video_id"] == "test_video"
    assert payload["retry_count"] == 1

    updated_task = db_session.get(Task, task.id)
    assert updated_task.status == TaskStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_internal_task_poll_timeout(client):
    response = await client.get(
        "/api/v2/internal/tasks?type=transcript&timeout=1",
        headers=_admin_headers(),
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_internal_task_submit_transcript_success(client, db_session):
    video = Video(video_id="transcript_video", title="Transcript Video")
    task = Task(
        task_type=internal_constants.FETCH_TRANSCRIPT_TASK_TYPE,
        status=TaskStatus.IN_PROGRESS,
        task_details={"video_id": "transcript_video"},
        retry_count=1,
        worker_details={"worker_user_id": None},
    )
    db_session.add_all([video, task])
    db_session.commit()

    response = await client.post(
        f"/api/v2/internal/tasks/{task.id}/result",
        headers=_admin_headers(),
        json={
            "video_id": "transcript_video",
            "success": True,
            "transcript": [{"text": "hello", "offset": 0}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"

    updated_video = db_session.get(Video, video.id)
    assert updated_video.transcript_available is True


@pytest.mark.asyncio
async def test_internal_ai_notes(client, db_session):
    video_id = "abc123DEF45"
    user = User(
        email="ai-notes@example.com",
        name="AI Notes User",
        profile_data={"ai_notes_enabled": True},
    )
    video = Video(video_id=video_id, title="AI Notes Video")
    db_session.add_all([user, video])
    db_session.commit()

    note = Note(
        video_id=video_id,
        timestamp="00:01",
        text=None,
        generated_by_ai=False,
        user_id=user.id,
    )
    db_session.add(note)
    db_session.commit()

    response = await client.get(
        f"/api/v2/internal/videos/{video_id}/ai-notes",
        headers=_admin_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["video_id"] == video_id
    assert len(payload["notes"]) == 1
