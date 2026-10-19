import pytest

from src.config import settings
from src.internal import constants as internal_constants
from src.internal.models import Task, TaskStatus
from src.internal import service as internal_service
from src.videos.models import Video


def admin_headers() -> dict[str, str]:
    return {"Authorization": (f"Bearer {settings.internal_api_admin_token}")}


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
        json={
            "summary": "Summary",
            "miscellaneous_data": {
                "suggested_questions": [
                    "What is the first idea?",
                    "How is the idea supported?",
                    "What conclusion is reached?",
                ]
            },
        },
    )
    assert summary_response.status_code == 200
    assert summary_response.json()["suggested_questions"] == [
        "What is the first idea?",
        "How is the idea supported?",
        "What conclusion is reached?",
    ]


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
async def test_internal_metrics_requires_admin_token(client):
    response = await client.get("/v2/internal/metrics")
    assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_internal_metrics_success(client):
    response = await client.get(
        "/v2/internal/metrics",
        headers=admin_headers(),
    )
    assert response.status_code == 200
    body = response.text
    assert "http_requests_total" in body or "http_request_duration_seconds" in body


@pytest.mark.asyncio
async def test_internal_summary_stores_key_points_without_dropping_them(
    client, db_session
):
    from src.videos.models import Video

    db_session.add(Video(video_id="kp123456789", title="Key points"))
    db_session.flush()
    questions = ["Question one here?", "Question two here?", "Question three here?"]
    points = [{"text": "Point", "start_seconds": 10, "end_seconds": 55.5}]

    stored = await client.post(
        "/v2/internal/videos/kp123456789/summary",
        headers=admin_headers(),
        json={
            "summary": "Summary",
            "miscellaneous_data": {
                "suggested_questions": questions,
                "key_points": points,
                "overview_model": "qwen/test",
            },
        },
    )
    assert stored.status_code == 200
    assert stored.json()["overview_model"] == "qwen/test"
    video = db_session.query(Video).filter_by(video_id="kp123456789").one()
    assert video.miscellaneous_data["overview_generated_at"]
    assert stored.json()["key_points"] == [
        {"text": "Point", "start_seconds": 10.0, "end_seconds": 55.5}
    ]

    # A later write with questions only keeps the existing key points.
    again = await client.post(
        "/v2/internal/videos/kp123456789/summary",
        headers=admin_headers(),
        json={"miscellaneous_data": {"suggested_questions": questions}},
    )
    assert again.json()["key_points"][0]["text"] == "Point"

    bad = await client.post(
        "/v2/internal/videos/kp123456789/summary",
        headers=admin_headers(),
        json={
            "miscellaneous_data": {
                "suggested_questions": questions,
                "key_points": [{"text": "x", "start_seconds": 9, "end_seconds": 1}],
            }
        },
    )
    assert bad.status_code == 422
