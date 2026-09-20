from datetime import datetime

import pytest
from src.auth.dependencies import get_current_user_id

from sqlalchemy.dialects import postgresql

from src.auth.models import User
from src.conversations.models import Conversation, Message
from src.notes.models import Note
from src.notes.service import search_notes
from src.videos.models import Video
from src.videos.schemas import VideoListParams
from src.videos.service import _library_query, get_library_summary, list_videos_for_user


def seed(db):
    users = [
        User(email="library-one@example.com"),
        User(email="library-two@example.com"),
    ]
    db.add_all(users)
    db.flush()
    videos = [
        Video(video_id=f"library{i:04d}", title=title)
        for i, title in enumerate(["100%_real", "Other title", "Chat only"])
    ]
    db.add_all(videos)
    db.flush()
    old, recent, newest = [datetime(2026, 9, day) for day in (1, 2, 3)]
    notes = [
        Note(
            video_id=videos[0].video_id,
            user_id=users[0].id,
            timestamp="01:02",
            text="a UNIQUE phrase 100%_real",
            generated_by_ai=True,
            created_at=old,
            updated_at=old,
        ),
        Note(
            video_id=videos[0].video_id,
            user_id=users[0].id,
            timestamp="02:03",
            text=None,
            created_at=old,
            updated_at=old,
        ),
        Note(
            video_id=videos[1].video_id,
            user_id=users[0].id,
            timestamp="00:01",
            text="unique second",
            created_at=recent,
            updated_at=recent,
        ),
        Note(
            video_id=videos[0].video_id,
            user_id=users[1].id,
            timestamp="00:01",
            text="unique private",
            generated_by_ai=True,
            created_at=newest,
            updated_at=newest,
        ),
    ]
    db.add_all(notes)
    conversations = [
        Conversation(video_id=videos[i].video_id, user_id=users[u].id)
        for i, u in [(0, 0), (0, 0), (2, 0), (1, 1)]
    ]
    db.add_all(conversations)
    db.flush()
    for index in (0, 2, 3):
        db.add_all(
            [
                Message(
                    conversation_id=conversations[index].id,
                    role=role,
                    content="hello",
                    created_at=newest,
                )
                for role in ("user", "assistant")
            ]
        )
    db.commit()
    return users, videos, notes, newest


def test_library_aggregates_are_owned_and_not_multiplied(db_session):
    users, videos, _, newest = seed(db_session)
    result = get_library_summary(db_session, users[0].id)
    assert (result.videos, result.notes, result.ai_notes, result.wiz_chats) == (
        2,
        3,
        1,
        1,
    )
    assert [v.video_id for v in result.recent_videos] == [
        videos[0].video_id,
        videos[1].video_id,
    ]
    assert result.recent_videos[0].note_count == 2
    assert result.recent_videos[0].last_activity_at == newest
    assert result.recent_videos[1].last_activity_at == datetime(2026, 9, 2)


def test_title_and_note_search_are_separate_literal_and_paginated(db_session):
    users, _, notes, _ = seed(db_session)
    uid = users[0].id
    titles = list_videos_for_user(db_session, uid, VideoListParams(q="unique"))
    assert titles.total == 0
    matches = search_notes(db_session, uid, "UNIQUE", 1, 1)
    assert (matches.total, matches.total_pages) == (2, 2)
    assert matches.notes[0].id == notes[2].id
    second = search_notes(db_session, uid, "unique", 2, 1)
    assert second.notes[0].id == notes[0].id
    assert second.notes[0].generated_by_ai
    assert "UNIQUE" in second.notes[0].excerpt
    assert search_notes(db_session, uid, "%_", 1, 10).total == 1
    assert list_videos_for_user(db_session, uid, VideoListParams(q="%_")).total == 1
    assert search_notes(db_session, uid, "missing", 1, 10).total == 0
    assert search_notes(db_session, uid, "unique", 3, 1).notes == []


def test_empty_library_and_stable_activity_pagination(db_session):
    users, videos, _, _ = seed(db_session)
    empty = get_library_summary(db_session, -1)
    assert (empty.videos, empty.notes, empty.ai_notes, empty.wiz_chats) == (0, 0, 0, 0)
    assert empty.recent_videos == []
    result = list_videos_for_user(
        db_session,
        users[0].id,
        VideoListParams(sort="activity_desc", page=2, per_page=1),
    )
    assert result.videos[0].video_id == videos[1].video_id
    # Compile the aggregate query for the production dialect as well as executing SQLite above.
    query, activity = _library_query(users[0].id)
    sql = str(query.order_by(activity.desc()).compile(dialect=postgresql.dialect()))
    assert "GROUP BY" in sql and "CASE WHEN" in sql


@pytest.mark.asyncio
async def test_dashboard_routes_and_query_validation(client, app, db_session):
    users, _, _, _ = seed(db_session)
    for url in ["/v2/videos/library-summary", "/v2/notes/search?q=unique"]:
        assert (await client.get(url)).status_code == 401
    app.dependency_overrides[get_current_user_id] = lambda: users[0].id
    try:
        summary = await client.get("/v2/videos/library-summary")
        assert summary.status_code == 200
        assert summary.json()["notes"] == 3
        videos = await client.get("/v2/videos?sort=activity_desc")
        assert videos.status_code == 200
        assert videos.json()["videos"][0]["note_count"] == 2
        notes = await client.get("/v2/notes/search?q=unique&page=1&per_page=1")
        assert notes.status_code == 200
        assert notes.json()["total_pages"] == 2
        for query in ["q=a", "q=%20%20", "q=unique&page=0", "q=unique&per_page=51"]:
            assert (await client.get("/v2/notes/search?" + query)).status_code in (
                400,
                422,
            )
    finally:
        app.dependency_overrides.pop(get_current_user_id)
