import asyncio
import json
from datetime import datetime
import pytest

from src.auth.models import User
from src.notes.models import Note
from src.videos import service as videos_service
from src.videos.models import Video
from src.videos.schemas import VideoListParams


def seed_video(db_session, video_id: str, title: str | None = None):
    video = Video(video_id=video_id, title=title)
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video


def test_list_videos_for_user_filters_and_sorts(db_session):
    user = User(email="videos@example.com", name="Videos User")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    video_a = seed_video(db_session, "abc123DEF45", "Alpha Video")
    video_b = seed_video(db_session, "xyz987LMN12", "Beta Video")

    db_session.add_all(
        [
            Note(video_id=video_a.video_id, timestamp="00:01", text="a", user_id=user.id),
            Note(video_id=video_b.video_id, timestamp="00:02", text="b", user_id=user.id),
        ]
    )
    db_session.commit()

    params = VideoListParams(q="Alpha", page=1, per_page=10, sort="title_asc")
    response = videos_service.list_videos_for_user(db_session, user.id, params)
    assert response.total == 1
    assert response.videos[0].video_id == "abc123DEF45"

    params = VideoListParams(q="", page=1, per_page=10, sort="title_desc")
    response = videos_service.list_videos_for_user(db_session, user.id, params)
    assert response.total == 2
    assert response.videos[0].video_id == "xyz987LMN12"


def test_list_videos_for_user_pagination(db_session):
    user = User(email="paging@example.com", name="Paging User")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    for index in range(3):
        video_id = f"vid{index:02d}ABCDE1"
        seed_video(db_session, video_id, f"Video {index}")
        db_session.add(
            Note(video_id=video_id, timestamp="00:01", text="note", user_id=user.id)
        )
    db_session.commit()

    params = VideoListParams(q="", page=1, per_page=2, sort="created_at_desc")
    response = videos_service.list_videos_for_user(db_session, user.id, params)
    assert response.total == 3
    assert response.total_pages == 2
    assert len(response.videos) == 2


def test_get_video_for_user_handles_multiple_notes(db_session):
    user = User(email="multi@example.com", name="Multi Notes")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    video = seed_video(db_session, "multi123456", "Multi")
    db_session.add_all(
        [
            Note(video_id=video.video_id, timestamp="00:01", text="a", user_id=user.id),
            Note(video_id=video.video_id, timestamp="00:02", text="b", user_id=user.id),
        ]
    )
    db_session.commit()

    result = videos_service.get_video_for_user(db_session, user.id, video.video_id)
    assert result is not None
    assert result.video_id == "multi123456"


def test_is_video_ready(db_session):
    video = seed_video(db_session, "ready123456", "Ready")
    assert videos_service.is_video_ready(video) is False

    video.video_metadata = {"title": "Ready"}
    video.transcript_available = True
    video.summary = "summary"
    assert videos_service.is_video_ready(video) is True


def test_format_event_payload(db_session):
    video = seed_video(db_session, "fmt1234567", "Format")
    video.video_metadata = {"title": "Format"}
    db_session.commit()

    event = videos_service._format_event("snapshot", video)
    assert event.startswith("event: snapshot")
    data_line = [line for line in event.splitlines() if line.startswith("data: ")][0]
    payload = json.loads(data_line.replace("data: ", "", 1))
    assert payload["event"] == "snapshot"
    assert payload["video"]["video_id"] == "fmt1234567"


def test_compute_total_pages_zero():
    assert videos_service._compute_total_pages(0, 10) == 0


@pytest.mark.asyncio
async def test_stream_video_events_emits_updates(monkeypatch):
    def make_video(video_id, metadata, transcript, summary):
        video = Video(video_id=video_id, title="Video")
        video.id = 1
        video.video_metadata = metadata
        video.transcript_available = transcript
        video.summary = summary
        now = datetime.utcnow()
        video.created_at = now
        video.updated_at = now
        return video

    sequence = [
        make_video("abc123DEF45", None, False, None),
        make_video("abc123DEF45", {"title": "Video"}, False, None),
        make_video("abc123DEF45", {"title": "Video"}, True, "summary"),
    ]

    async def fake_fetch(_video_id):
        return sequence.pop(0) if sequence else None

    async def fake_sleep(_):
        return None

    monkeypatch.setattr(videos_service, "_fetch_video", fake_fetch)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    events = []
    async for chunk in videos_service.stream_video_events("abc123DEF45"):
        if chunk.startswith("event:"):
            events.append(chunk.splitlines()[0].replace("event: ", ""))

    assert events[0] == "snapshot"
    assert "update" in events
    assert events[-1] == "done"


@pytest.mark.asyncio
async def test_stream_video_events_no_video(monkeypatch):
    async def fake_fetch(_video_id):
        return None

    monkeypatch.setattr(videos_service, "_fetch_video", fake_fetch)
    events = [chunk async for chunk in videos_service.stream_video_events("abc123DEF45")]
    assert events == []


@pytest.mark.asyncio
async def test_stream_video_events_immediate_done(monkeypatch):
    def make_video():
        video = Video(video_id="abc123DEF45", title="Video")
        video.id = 1
        video.video_metadata = {"title": "Video"}
        video.transcript_available = True
        video.summary = "summary"
        now = datetime.utcnow()
        video.created_at = now
        video.updated_at = now
        return video

    async def fake_fetch(_video_id):
        return make_video()

    monkeypatch.setattr(videos_service, "_fetch_video", fake_fetch)
    events = []
    async for chunk in videos_service.stream_video_events("abc123DEF45"):
        if chunk.startswith("event:"):
            events.append(chunk.splitlines()[0].replace("event: ", ""))
    assert events == ["snapshot", "done"]


@pytest.mark.asyncio
async def test_stream_video_events_stop_when_missing_in_loop(monkeypatch):
    def make_video():
        video = Video(video_id="abc123DEF45", title="Video")
        video.id = 1
        video.video_metadata = None
        video.transcript_available = False
        video.summary = None
        now = datetime.utcnow()
        video.created_at = now
        video.updated_at = now
        return video

    calls = {"count": 0}

    async def fake_fetch(_video_id):
        calls["count"] += 1
        if calls["count"] == 1:
            return make_video()
        return None

    async def fake_sleep(_):
        return None

    monkeypatch.setattr(videos_service, "_fetch_video", fake_fetch)
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    events = [chunk async for chunk in videos_service.stream_video_events("abc123DEF45")]
    assert events


@pytest.mark.asyncio
async def test_fetch_video_uses_sessionlocal(monkeypatch):
    captured = {"closed": False}

    class _Session:
        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(videos_service, "SessionLocal", lambda: _Session())
    monkeypatch.setattr(
        videos_service,
        "get_video_by_id",
        lambda db, video_id: "video",
    )

    async def run_in_threadpool(fn):
        return fn()

    monkeypatch.setattr(videos_service, "run_in_threadpool", run_in_threadpool)

    result = await videos_service._fetch_video("abc123DEF45")
    assert result == "video"
    assert captured["closed"] is True
