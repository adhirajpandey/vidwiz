import jwt
import pytest

from src.auth import service as auth_service
from src.config import settings
from src.videos.models import Video


def make_token(user_id: int, email: str) -> str:
    return jwt.encode(
        {"user_id": user_id, "email": email, "name": "Video User"},
        settings.secret_key,
        algorithm="HS256",
    )


@pytest.mark.asyncio
async def test_get_video(client, db_session):
    user = auth_service.create_user(
        db_session,
        "videos-list@example.com",
        "Videos User",
        "password123",
    )
    token = make_token(user.id, user.email)
    headers = {"Authorization": f"Bearer {token}"}

    video = Video(video_id="list1234567", title="List Video")
    db_session.add(video)
    db_session.commit()

    get_response = await client.get("/v2/videos/list1234567", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["video_id"] == "list1234567"


@pytest.mark.asyncio
async def test_guest_can_read_video(client, db_session):
    db_session.add(Video(video_id="guest123456", title="Guest"))
    db_session.commit()

    response = await client.get(
        "/v2/videos/guest123456", headers={"X-Guest-Session-ID": "guest-1"}
    )
    anonymous = await client.get("/v2/videos/guest123456")

    assert response.status_code == 200
    assert anonymous.status_code == 401


@pytest.mark.asyncio
async def test_ask_status_reflects_the_one_time_charge(client, db_session, user):
    from src.credits import service as credits_service

    db_session.add(Video(video_id="ask12345678", title="Ask"))
    db_session.commit()
    headers = {"Authorization": f"Bearer {make_token(user.id, user.email)}"}

    before = await client.get("/v2/videos/ask12345678/ask-status", headers=headers)
    credits_service.charge_wiz_chat_for_video(db_session, user.id, "ask12345678")
    after = await client.get("/v2/videos/ask12345678/ask-status", headers=headers)
    guest = await client.get(
        "/v2/videos/ask12345678/ask-status", headers={"X-Guest-Session-ID": "g"}
    )

    assert before.json() == {"unlocked": False, "cost": 5}
    assert after.json() == {"unlocked": True, "cost": 5}
    assert guest.json() == {"unlocked": True, "cost": 0}


@pytest.mark.asyncio
async def test_retry_overview_requires_sign_in_and_a_failed_overview(
    client, db_session, monkeypatch
):
    from src.videos import overview
    from src.videos.models import OverviewStatus, TranscriptStatus

    sent = []
    monkeypatch.setattr(
        overview, "send_job", lambda _url, payload: sent.append(payload)
    )
    user = auth_service.create_user(
        db_session, "retry@example.com", "Retry User", "password123"
    )
    headers = {"Authorization": f"Bearer {make_token(user.id, user.email)}"}
    db_session.add(
        Video(
            video_id="retryroute1",
            transcript_status=TranscriptStatus.READY,
            overview_status=OverviewStatus.FAILED,
        )
    )
    db_session.commit()

    guest = await client.post(
        "/v2/videos/retryroute1/overview/retry", headers={"X-Guest-Session-ID": "g"}
    )
    retried = await client.post(
        "/v2/videos/retryroute1/overview/retry", headers=headers
    )
    again = await client.post("/v2/videos/retryroute1/overview/retry", headers=headers)

    assert guest.status_code == 401
    assert retried.status_code == 200
    assert retried.json()["overview_status"] == "queued"
    assert sent == [{"video_id": "retryroute1"}]
    assert again.status_code == 400
