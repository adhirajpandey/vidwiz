from datetime import datetime, time, timedelta

import pytest
from sqlalchemy import func, select

from src.auth import service as auth_service
from src.moments import service
from src.moments.models import CaptureSource, Moment, ResolveStatus
from src.tests.test_moments import auth_headers
from src.videos.models import Video


def test_resurface_excludes_ineligible_and_private_moments(db_session, user):
    other = auth_service.create_user(
        db_session, "other@example.com", "Other", "pw123456"
    )
    today = db_session.scalar(select(func.current_date()))
    cutoff = datetime.combine(today, time()) - timedelta(days=60)
    db_session.add(Video(video_id="aaaaaaaaaaa", title="A video"))
    db_session.flush()

    def add(**fields):
        values = dict(
            user_id=user.id,
            video_id="aaaaaaaaaaa",
            at_seconds=20,
            note="A useful older thought",
            source=CaptureSource.WEB,
            created_at=cutoff - timedelta(days=1),
        )
        values.update(fields)
        moment = Moment(**values)
        db_session.add(moment)
        db_session.flush()
        return moment.id

    eligible = {
        add(),
        add(note=None, quote="A quoted passage to remember"),
        add(note=None, ai_text="An AI line to remember"),
    }
    add(user_id=other.id)
    add(created_at=cutoff)  # Strictly older, not at the cutoff.
    add(created_at=cutoff + timedelta(days=1))
    add(note="dope")
    add(note="   ", quote=None)
    add(video_id=None, resolve_status=ResolveStatus.UNRESOLVED)
    results = [service.resurface(db_session, user.id, skip) for skip in range(3)]
    assert {r.moment.id for r in results} == eligible
    assert all(
        r.state == "found" and r.moment.video_title == "A video" for r in results
    )
    assert [
        service.resurface(db_session, user.id, skip).moment.id for skip in range(3)
    ] == [r.moment.id for r in results]
    assert service.resurface(db_session, user.id, 3).state == "none"


@pytest.mark.asyncio
async def test_resurface_route_empty_and_auth(client, user):
    assert (await client.get("/v2/moments/resurface")).status_code == 401
    response = await client.get("/v2/moments/resurface", headers=auth_headers(user))
    assert response.status_code == 200
    assert response.json() == {"state": "none"}
    assert (
        await client.get("/v2/moments/resurface?skip=-1", headers=auth_headers(user))
    ).status_code == 422
