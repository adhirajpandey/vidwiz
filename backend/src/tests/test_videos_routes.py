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
