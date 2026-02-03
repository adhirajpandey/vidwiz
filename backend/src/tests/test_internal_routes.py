import pytest

from src.config import settings
from src.internal import constants as internal_constants
from src.internal.models import Task, TaskStatus
from src.internal import service as internal_service
from src.auth.models import User
from src.notes.models import Note
from src.videos.models import Video


def admin_headers() -> dict[str, str]:
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
        "/v2/internal/tasks?type=transcript&timeout=1",
        headers=admin_headers(),
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
        "/v2/internal/tasks?type=transcript&timeout=1",
        headers=admin_headers(),
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_internal_task_submit_transcript_success(client, db_session, monkeypatch):
    monkeypatch.setattr(
        internal_service, "store_transcript_in_s3", lambda *_args, **_kwargs: None
    )
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
        f"/v2/internal/tasks/{task.id}/result",
        headers=admin_headers(),
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
        f"/v2/internal/videos/{video_id}/ai-notes",
        headers=admin_headers(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["video_id"] == video_id
    assert len(payload["notes"]) == 1


@pytest.mark.asyncio
async def test_internal_ai_notes_not_found(client, db_session):
    video_id = "abc123DEF45"
    video = Video(video_id=video_id, title="AI Notes Video")
    db_session.add(video)
    db_session.commit()

    response = await client.get(
        f"/v2/internal/videos/{video_id}/ai-notes",
        headers=admin_headers(),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_internal_ai_notes_video_missing(client):
    response = await client.get(
        "/v2/internal/videos/abc123DEF45/ai-notes",
        headers=admin_headers(),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_internal_store_transcript_metadata_summary(client, monkeypatch):
    monkeypatch.setattr(
        internal_service, "store_transcript_in_s3", lambda *_args, **_kwargs: None
    )
    video_id = "abc123DEF45"

    transcript_response = await client.post(
        f"/v2/internal/videos/{video_id}/transcript",
        headers=admin_headers(),
        json={"transcript": [{"text": "hello"}]},
    )
    assert transcript_response.status_code == 200

    metadata_response = await client.post(
        f"/v2/internal/videos/{video_id}/metadata",
        headers=admin_headers(),
        json={"metadata": {"title": "Video"}},
    )
    assert metadata_response.status_code == 200

    summary_response = await client.post(
        f"/v2/internal/videos/{video_id}/summary",
        headers=admin_headers(),
        json={"summary": "Summary"},
    )
    assert summary_response.status_code == 200


@pytest.mark.asyncio
async def test_internal_get_video_not_found(client):
    response = await client.get(
        "/v2/internal/videos/abc123DEF45",
        headers=admin_headers(),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_internal_get_video_success(client):
    video_id = "abc123DEF45"
    await client.post(
        f"/v2/internal/videos/{video_id}/metadata",
        headers=admin_headers(),
        json={"metadata": {"title": "Video"}},
    )

    response = await client.get(
        f"/v2/internal/videos/{video_id}",
        headers=admin_headers(),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["video_id"] == video_id


@pytest.mark.asyncio
async def test_internal_update_note_not_found(client):
    response = await client.patch(
        "/v2/internal/notes/9999",
        headers=admin_headers(),
        json={"text": "updated"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_internal_update_note_success(client, db_session):
    video = Video(video_id="abc123DEF45", title="Video")
    note = Note(video_id=video.video_id, timestamp="00:01", text="hi", user_id=1)
    db_session.add_all([video, note])
    db_session.commit()

    response = await client.patch(
        f"/v2/internal/notes/{note.id}",
        headers=admin_headers(),
        json={"text": "updated"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == "updated"
