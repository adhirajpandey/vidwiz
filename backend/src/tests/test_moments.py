from datetime import datetime, timezone

import jwt
import pytest

from src import transcripts
from src.auth import service as auth_service
from src.config import settings
from src.credits.models import CreditsLedger
from src.internal import constants as internal_constants
from src.internal.models import Task, TaskStatus
from src.library.models import LibraryItem
from src.moments import service as moments_service
from src.moments.models import AiStatus, CaptureSource, Moment, ResolveStatus
from src.moments.schemas import CaptureCreate, parse_seconds
from src.shared import queues
from src.videos.models import TranscriptStatus, Video

VIDEO_ID = "abc123DEF45"
TRANSCRIPT = [
    {"text": "earlier point", "offset": 10, "duration": 4},
    {"text": "thirty seconds ago", "offset": 70, "duration": 4},
    {"text": "composite index order matters", "offset": 95, "duration": 5},
    {"text": "the leftmost column comes first", "offset": 100, "duration": 5},
    {"text": "much later", "offset": 300, "duration": 5},
]


def auth_headers(user) -> dict[str, str]:
    token = jwt.encode(
        {"user_id": user.id, "email": user.email, "name": user.name},
        settings.secret_key,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {settings.internal_api_admin_token}"}


@pytest.fixture
def sent_jobs(monkeypatch):
    """Record AI moment jobs sent to SQS."""
    jobs = []

    class Sqs:
        def send_message(self, QueueUrl, MessageBody):
            jobs.append(MessageBody)
            return {}

    monkeypatch.setattr(queues.boto3, "client", lambda *_a, **_k: Sqs())
    return jobs


@pytest.fixture
def transcript_ready(db_session, monkeypatch):
    db_session.add(
        Video(
            video_id=VIDEO_ID, title="Indexes", transcript_status=TranscriptStatus.READY
        )
    )
    db_session.flush()
    monkeypatch.setattr(transcripts, "load_transcript", lambda _video_id: TRANSCRIPT)


def charges(db_session, user) -> list[CreditsLedger]:
    return (
        db_session.query(CreditsLedger)
        .filter(CreditsLedger.user_id == user.id, CreditsLedger.reason == "ai_moment")
        .all()
    )


def capture(db_session, user, **fields):
    fields.setdefault("video", VIDEO_ID)
    fields.setdefault("at", 100)
    fields.setdefault("ai", False)
    return moments_service.capture(db_session, user.id, CaptureCreate(**fields))


@pytest.mark.parametrize(
    ("value", "seconds"), [(75, 75), ("75", 75), ("1:15", 75), ("1:01:15", 3675)]
)
def test_parse_seconds(value, seconds):
    assert parse_seconds(value) == seconds


@pytest.mark.parametrize("value", ["-1:00", "abc", "1:75", -3])
def test_parse_seconds_rejects_invalid(value):
    with pytest.raises(ValueError):
        parse_seconds(value)


def test_capture_requires_video_or_title():
    with pytest.raises(ValueError):
        CaptureCreate(at=10)


def test_capture_saves_moment_library_item_and_schedules_video(db_session, user):
    moment, merged = capture(db_session, user, note="  my thought  ")

    assert merged is False
    assert moment.video_id == VIDEO_ID
    assert moment.note == "my thought"
    assert moment.ai_status == AiStatus.NOT_REQUESTED
    assert moment.resolve_status == ResolveStatus.RESOLVED
    assert db_session.get(LibraryItem, (user.id, VIDEO_ID)) is not None
    task_types = {task.task_type for task in db_session.query(Task).all()}
    assert task_types == {
        internal_constants.FETCH_METADATA_TASK_TYPE,
        internal_constants.FETCH_TRANSCRIPT_TASK_TYPE,
    }


def test_capture_with_transcript_adds_quote_and_queues_ai_once(
    db_session, user, transcript_ready, sent_jobs
):
    moment, _ = capture(db_session, user, ai=True)

    assert moment.ai_status == AiStatus.QUEUED
    assert moment.quote == (
        "composite index order matters the leftmost column comes first"
    )
    assert moment.quote_start_seconds == 95
    assert len(sent_jobs) == 1
    assert len(charges(db_session, user)) == 1

    # A second tap nearby merges without another charge or job.
    again, merged = capture(db_session, user, at=105, ai=True)
    assert merged is True
    assert again.id == moment.id
    assert len(sent_jobs) == 1
    assert len(charges(db_session, user)) == 1


def test_capture_without_transcript_waits_and_does_not_charge(
    db_session, user, sent_jobs
):
    moment, _ = capture(db_session, user, ai=True)

    assert moment.ai_status == AiStatus.WAITING_TRANSCRIPT
    assert moment.quote is None
    assert sent_jobs == []
    assert charges(db_session, user) == []


def test_capture_uses_the_users_ai_default(
    db_session, user, transcript_ready, sent_jobs
):
    user.profile_data = {"ai_moments_default": True}
    db_session.flush()

    moment, _ = capture(db_session, user, ai=None)

    assert moment.ai_status == AiStatus.QUEUED


def test_capture_without_credits_keeps_the_moment(
    db_session, user, transcript_ready, sent_jobs
):
    user.credits_balance = 0
    db_session.flush()

    moment, _ = capture(db_session, user, ai=True)

    assert moment.id is not None
    assert moment.ai_status == AiStatus.INSUFFICIENT_CREDITS
    assert sent_jobs == []


def test_dedupe_window_merges_notes_within_ten_seconds(db_session, user):
    first, _ = capture(db_session, user, at=100, note="one")
    merged, was_merged = capture(db_session, user, at=110, note="two")
    separate, was_separate_merged = capture(db_session, user, at=111)

    assert was_merged is True
    assert merged.id == first.id
    assert merged.note == "one\ntwo"
    assert was_separate_merged is False
    assert separate.id != first.id


def test_failed_queue_marks_moment_failed_and_retry_does_not_recharge(
    db_session, user, transcript_ready, monkeypatch
):
    class BrokenSqs:
        def send_message(self, **_kwargs):
            raise RuntimeError("queue down")

    monkeypatch.setattr(queues.boto3, "client", lambda *_a, **_k: BrokenSqs())
    moment, _ = capture(db_session, user, ai=True)
    assert moment.ai_status == AiStatus.FAILED

    jobs = []
    monkeypatch.setattr(
        queues.boto3,
        "client",
        lambda *_a, **_k: type(
            "Sqs", (), {"send_message": lambda self, **k: jobs.append(k)}
        )(),
    )
    retried = moments_service.request_ai(db_session, moment)

    assert retried.ai_status == AiStatus.QUEUED
    assert len(jobs) == 1
    assert len(charges(db_session, user)) == 1


def test_title_capture_resolves_from_library_instantly(db_session, user):
    capture(db_session, user, at=10)
    db_session.query(Video).filter_by(video_id=VIDEO_ID).one().title = "Deep Focus"
    db_session.flush()

    moment, _ = capture(db_session, user, video=None, title="deep focus", at=500)

    assert moment.video_id == VIDEO_ID
    assert moment.resolve_status == ResolveStatus.RESOLVED


def test_title_capture_queues_resolution(db_session, user):
    moment, merged = capture(
        db_session, user, video=None, title="Unknown Talk", channel="Chan", ai=True
    )

    assert merged is False
    assert moment.video_id is None
    assert moment.resolve_status == ResolveStatus.RESOLVING
    assert moment.ai_status == AiStatus.WAITING_TRANSCRIPT
    task = (
        db_session.query(Task)
        .filter(Task.task_type == internal_constants.RESOLVE_TITLE_TASK_TYPE)
        .one()
    )
    assert task.task_details == {
        "moment_id": moment.id,
        "title": "Unknown Talk",
        "channel": "Chan",
    }


def _claim_resolve_task(db_session) -> Task:
    task = (
        db_session.query(Task)
        .filter(Task.task_type == internal_constants.RESOLVE_TITLE_TASK_TYPE)
        .one()
    )
    task.status = TaskStatus.IN_PROGRESS
    task.retry_count = 1
    db_session.flush()
    return task


@pytest.mark.asyncio
async def test_resolve_task_result_attaches_video(client, db_session, user):
    moment, _ = capture(db_session, user, video=None, title="Unknown Talk")
    task = _claim_resolve_task(db_session)

    response = await client.post(
        f"/v2/internal/tasks/{task.id}/result",
        headers=admin_headers(),
        json={
            "success": True,
            "resolved": {"video_id": VIDEO_ID, "title": "Unknown Talk"},
        },
    )

    assert response.status_code == 200
    db_session.refresh(moment)
    assert moment.video_id == VIDEO_ID
    assert moment.resolve_status == ResolveStatus.RESOLVED
    assert moment.pending_title is None
    assert db_session.get(LibraryItem, (user.id, VIDEO_ID)) is not None


@pytest.mark.asyncio
async def test_resolve_task_result_merges_into_nearby_moment(client, db_session, user):
    existing, _ = capture(db_session, user, at=100, note="first")
    pending, _ = capture(
        db_session, user, video=None, title="Unknown Talk", at=104, note="second"
    )
    task = _claim_resolve_task(db_session)

    response = await client.post(
        f"/v2/internal/tasks/{task.id}/result",
        headers=admin_headers(),
        json={"success": True, "resolved": {"video_id": VIDEO_ID}},
    )

    assert response.status_code == 200
    db_session.refresh(existing)
    assert existing.note == "first\nsecond"
    assert db_session.get(Moment, pending.id) is None


@pytest.mark.asyncio
async def test_final_resolve_failure_marks_moment_unresolved(client, db_session, user):
    moment, _ = capture(db_session, user, video=None, title="Unknown", ai=True)
    task = _claim_resolve_task(db_session)
    task.retry_count = internal_constants.TASK_MAX_RETRIES
    db_session.flush()

    response = await client.post(
        f"/v2/internal/tasks/{task.id}/result",
        headers=admin_headers(),
        json={"success": False, "error_message": "no results"},
    )

    assert response.status_code == 200
    db_session.refresh(moment)
    assert moment.resolve_status == ResolveStatus.UNRESOLVED
    assert moment.ai_status == AiStatus.FAILED


@pytest.mark.asyncio
async def test_resolve_task_requires_resolved_video(client, db_session, user):
    capture(db_session, user, video=None, title="Unknown")
    task = _claim_resolve_task(db_session)

    response = await client.post(
        f"/v2/internal/tasks/{task.id}/result",
        headers=admin_headers(),
        json={"success": True},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_transcript_result_fills_quotes_and_failure_marks_no_transcript(
    client, db_session, user, monkeypatch
):
    from src.internal import service as internal_service

    monkeypatch.setattr(internal_service, "store_transcript_in_s3", lambda *_a: None)
    moment, _ = capture(db_session, user, ai=True)
    task = (
        db_session.query(Task)
        .filter(Task.task_type == internal_constants.FETCH_TRANSCRIPT_TASK_TYPE)
        .one()
    )
    task.status = TaskStatus.IN_PROGRESS
    task.retry_count = 1
    db_session.flush()

    response = await client.post(
        f"/v2/internal/tasks/{task.id}/result",
        headers=admin_headers(),
        json={"video_id": VIDEO_ID, "success": True, "transcript": TRANSCRIPT},
    )
    assert response.status_code == 200
    db_session.refresh(moment)
    assert moment.quote_start_seconds == 95
    # Charging and queueing happen when the dispatcher collects the moment.
    assert moment.ai_status == AiStatus.WAITING_TRANSCRIPT

    other, _ = capture(db_session, user, video="zzz123ZZZ45", ai=True)
    failing = (
        db_session.query(Task)
        .filter(
            Task.task_type == internal_constants.FETCH_TRANSCRIPT_TASK_TYPE,
            Task.status == TaskStatus.PENDING,
        )
        .one()
    )
    failing.status = TaskStatus.IN_PROGRESS
    failing.retry_count = internal_constants.TASK_MAX_RETRIES
    db_session.flush()
    response = await client.post(
        f"/v2/internal/tasks/{failing.id}/result",
        headers=admin_headers(),
        json={"video_id": "zzz123ZZZ45", "success": False, "error_message": "none"},
    )
    assert response.status_code == 200
    db_session.refresh(other)
    assert other.ai_status == AiStatus.NO_TRANSCRIPT


@pytest.mark.asyncio
async def test_pending_moments_charges_queues_and_flags_missing_credits(
    client, db_session, user
):
    poor = auth_service.create_user(db_session, "poor@example.com", "Poor", "pw123456")
    poor.credits_balance = 0
    db_session.flush()
    mine, _ = capture(db_session, user, ai=True)
    theirs, _ = capture(db_session, poor, ai=True)
    db_session.query(Video).filter_by(
        video_id=VIDEO_ID
    ).one().transcript_status = TranscriptStatus.READY
    db_session.flush()

    response = await client.post(
        f"/v2/internal/videos/{VIDEO_ID}/pending-moments", headers=admin_headers()
    )

    assert response.status_code == 200
    assert response.json() == {
        "video_id": VIDEO_ID,
        "moments": [
            {"id": mine.id, "video_id": VIDEO_ID, "at_seconds": 100, "user_id": user.id}
        ],
    }
    db_session.refresh(mine)
    db_session.refresh(theirs)
    assert mine.ai_status == AiStatus.QUEUED
    assert theirs.ai_status == AiStatus.INSUFFICIENT_CREDITS
    assert len(charges(db_session, user)) == 1


@pytest.mark.asyncio
async def test_internal_ai_write_sets_ready_or_failed(client, db_session, user):
    moment, _ = capture(db_session, user)

    response = await client.put(
        f"/v2/internal/moments/{moment.id}/ai",
        headers=admin_headers(),
        json={"ai_text": "Index order matters", "ai_model": "z-ai/test"},
    )
    assert response.status_code == 200
    assert response.json()["ai_status"] == "ready"
    assert response.json()["ai_model"] == "z-ai/test"
    assert response.json()["ai_text"] == "Index order matters"

    # A late failure report leaves a ready line alone.
    response = await client.put(
        f"/v2/internal/moments/{moment.id}/ai",
        headers=admin_headers(),
        json={"ai_text": None},
    )
    assert response.json()["ai_status"] == "ready"

    moment.ai_status = AiStatus.QUEUED
    db_session.commit()
    response = await client.put(
        f"/v2/internal/moments/{moment.id}/ai",
        headers=admin_headers(),
        json={"ai_text": None},
    )
    assert response.json()["ai_status"] == "failed"

    missing = await client.put(
        "/v2/internal/moments/999999/ai", headers=admin_headers(), json={}
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_capture_route_with_api_token_and_merge_status(client, db_session, user):
    _, token = auth_service.create_api_token(db_session, user.id, "Phone")
    headers = {"Authorization": f"Bearer {token}"}
    body = {"video": f"https://youtu.be/{VIDEO_ID}", "at": "1:40", "source": "phone"}

    created = await client.post("/v2/captures", headers=headers, json=body)
    merged = await client.post("/v2/captures", headers=headers, json=body)

    assert created.status_code == 201
    assert created.json()["merged"] is False
    assert created.json()["moment"]["at_seconds"] == 100
    assert created.json()["moment"]["source"] == "phone"
    assert merged.status_code == 200
    assert merged.json()["merged"] is True


@pytest.mark.asyncio
async def test_capture_route_validation(client, user):
    response = await client.post(
        "/v2/captures", headers=auth_headers(user), json={"at": 5}
    )
    assert response.status_code == 422

    response = await client.post(
        "/v2/captures",
        headers=auth_headers(user),
        json={"video": VIDEO_ID, "at": 5, "source": "legacy"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_legacy_extension_route_creates_moment(client, db_session, user):
    response = await client.post(
        f"/v2/videos/{VIDEO_ID}/notes",
        headers=auth_headers(user),
        json={"timestamp": "2:05", "text": "note", "video_title": "Indexes"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["at_seconds"] == 125
    assert payload["note"] == "note"
    assert payload["source"] == "extension"
    assert payload["ai_status"] == "not_requested"


@pytest.mark.asyncio
async def test_moment_read_update_delete_routes(client, db_session, user):
    later, _ = capture(db_session, user, at=200, note="later")
    earlier, _ = capture(db_session, user, at=50)
    headers = auth_headers(user)

    listed = await client.get(f"/v2/videos/{VIDEO_ID}/moments", headers=headers)
    assert [item["id"] for item in listed.json()] == [earlier.id, later.id]

    feed = await client.get("/v2/moments?per_page=1", headers=headers)
    assert feed.json()["moments"][0]["id"] == earlier.id
    assert feed.json()["has_more"] is True

    updated = await client.patch(
        f"/v2/moments/{later.id}",
        headers=headers,
        json={"note": None, "ai_text": "Edited"},
    )
    assert updated.json()["note"] is None
    assert updated.json()["ai_text"] == "Edited"

    empty = await client.patch(f"/v2/moments/{later.id}", headers=headers, json={})
    assert empty.status_code == 400

    deleted = await client.delete(f"/v2/moments/{later.id}", headers=headers)
    assert deleted.status_code == 200
    gone = await client.patch(
        f"/v2/moments/{later.id}", headers=headers, json={"note": "x"}
    )
    assert gone.status_code == 404


@pytest.mark.asyncio
async def test_moments_are_private(client, db_session, user):
    moment, _ = capture(db_session, user)
    other = auth_service.create_user(
        db_session, "other@example.com", "Other", "pw123456"
    )

    response = await client.patch(
        f"/v2/moments/{moment.id}", headers=auth_headers(other), json={"note": "x"}
    )
    listed = await client.get(
        f"/v2/videos/{VIDEO_ID}/moments", headers=auth_headers(other)
    )

    assert response.status_code == 404
    assert listed.json() == []


@pytest.mark.asyncio
async def test_request_ai_route_rejects_ready_moment(client, db_session, user):
    moment, _ = capture(db_session, user)
    moments_service.save_ai_text(db_session, moment, "Done")

    response = await client.post(
        f"/v2/moments/{moment.id}/ai", headers=auth_headers(user)
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_save_passage_keeps_cited_text_without_ai(
    client, db_session, user, transcript_ready, sent_jobs
):
    headers = auth_headers(user)
    body = {"video_id": VIDEO_ID, "start_seconds": 95, "end_seconds": 104.5}

    created = await client.post("/v2/moments/passages", headers=headers, json=body)
    merged = await client.post(
        "/v2/moments/passages", headers=headers, json={**body, "note": "keep this"}
    )
    missing = await client.post(
        "/v2/moments/passages",
        headers=headers,
        json={**body, "video_id": "zzzzzzzzzzz"},
    )
    backwards = await client.post(
        "/v2/moments/passages",
        headers=headers,
        json={**body, "start_seconds": 120},
    )

    assert created.status_code == 201
    moment = created.json()["moment"]
    assert moment["quote"] == (
        "composite index order matters the leftmost column comes first"
    )
    assert moment["quote_start_seconds"] == 95
    assert moment["ai_status"] == "not_requested"
    assert moment["source"] == "web"
    assert merged.status_code == 200
    assert merged.json()["moment"]["note"] == "keep this"
    assert missing.status_code == 404
    assert backwards.status_code == 422
    assert sent_jobs == []
    assert charges(db_session, user) == []


@pytest.mark.asyncio
async def test_markdown_exports(client, db_session, user, transcript_ready):
    moment, _ = capture(db_session, user, at=100, note="Order\nmatters")
    moments_service.save_ai_text(db_session, moment, "Index order matters")
    db_session.add(Video(video_id="emptyvideo1", title="Nothing here"))
    db_session.flush()
    db_session.add(LibraryItem(user_id=user.id, video_id="emptyvideo1"))
    db_session.flush()
    headers = auth_headers(user)

    video = await client.get(f"/v2/videos/{VIDEO_ID}/export.md", headers=headers)
    library = await client.get("/v2/library/export.md", headers=headers)
    missing = await client.get("/v2/videos/zzzzzzzzzzz/export.md", headers=headers)

    assert video.status_code == 200
    assert video.headers["content-type"].startswith("text/markdown")
    assert video.text.splitlines()[:5] == [
        f"# [Indexes](https://youtu.be/{VIDEO_ID})",
        "",
        f"- [1:40](https://youtu.be/{VIDEO_ID}?t=95)",
        "  - Order matters",
        "  - AI: Index order matters",
    ]
    assert library.text.startswith("# VidWiz library")
    assert f"## [Indexes](https://youtu.be/{VIDEO_ID})" in library.text
    assert "Nothing here" not in library.text
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_ambiguous_title_offers_candidates_and_user_picks(
    client, db_session, user
):
    moment, _ = capture(db_session, user, video=None, title="Focus", ai=True)
    task = _claim_resolve_task(db_session)
    candidates = [
        {"video_id": VIDEO_ID, "title": "Focus part 1", "channel": "A"},
        {"video_id": "zzz123ZZZ45", "title": "Focus part 2", "channel": "B"},
    ]

    response = await client.post(
        f"/v2/internal/tasks/{task.id}/result",
        headers=admin_headers(),
        json={"success": True, "candidates": candidates},
    )
    assert response.status_code == 200
    db_session.refresh(moment)
    assert moment.resolve_status == ResolveStatus.UNRESOLVED
    assert moment.ai_status == AiStatus.WAITING_TRANSCRIPT

    listed = (await client.get("/v2/moments", headers=auth_headers(user))).json()
    assert listed["moments"][0]["resolve_candidates"] == candidates

    wrong = await client.post(
        f"/v2/moments/{moment.id}/resolve",
        headers=auth_headers(user),
        json={"video_id": "notachoice1"},
    )
    assert wrong.status_code == 400

    picked = await client.post(
        f"/v2/moments/{moment.id}/resolve",
        headers=auth_headers(user),
        json={"video_id": "zzz123ZZZ45"},
    )
    assert picked.status_code == 200
    payload = picked.json()
    assert payload["video_id"] == "zzz123ZZZ45"
    assert payload["resolve_status"] == "resolved"
    assert payload["resolve_candidates"] is None
    # Still waiting for the transcript, so the AI request carries over.
    assert payload["ai_status"] == "waiting_transcript"

    again = await client.post(
        f"/v2/moments/{moment.id}/resolve",
        headers=auth_headers(user),
        json={"video_id": "zzz123ZZZ45"},
    )
    assert again.status_code == 400


@pytest.mark.asyncio
async def test_title_result_needs_exactly_one_outcome(client, db_session, user):
    capture(db_session, user, video=None, title="Focus")
    task = _claim_resolve_task(db_session)

    both = await client.post(
        f"/v2/internal/tasks/{task.id}/result",
        headers=admin_headers(),
        json={
            "success": True,
            "resolved": {"video_id": VIDEO_ID},
            "candidates": [{"video_id": VIDEO_ID}],
        },
    )
    assert both.status_code == 400


def test_sweep_fails_only_stale_queued_ai_lines(db_session, user):
    from datetime import datetime, timedelta

    from sqlalchemy import update

    stale, _ = capture(db_session, user)
    fresh = Moment(
        user_id=user.id,
        video_id=VIDEO_ID,
        at_seconds=500,
        ai_status=AiStatus.QUEUED,
        source=CaptureSource.WEB,
    )
    db_session.add(fresh)
    stale.ai_status = AiStatus.QUEUED
    db_session.commit()
    db_session.execute(
        update(Moment)
        .where(Moment.id == stale.id)
        .values(updated_at=datetime.utcnow() - timedelta(hours=1))
    )
    db_session.commit()

    assert moments_service.sweep_stale_ai(db_session, timedelta(minutes=30)) == 1
    db_session.refresh(stale)
    db_session.refresh(fresh)
    assert stale.ai_status == AiStatus.FAILED
    assert fresh.ai_status == AiStatus.QUEUED


def test_backfill_quotes_fills_imported_moments(db_session, user, monkeypatch):
    from src import database
    from src.management import backfill

    db_session.add_all(
        [
            Video(
                video_id=VIDEO_ID, title="A", transcript_status=TranscriptStatus.READY
            ),
            Video(
                video_id="bbbbbbbbbbb",
                title="B",
                transcript_status=TranscriptStatus.PENDING,
            ),
        ]
    )
    db_session.flush()
    imported = Moment(
        user_id=user.id, video_id=VIDEO_ID, at_seconds=100, source=CaptureSource.LEGACY
    )
    quoted = Moment(
        user_id=user.id,
        video_id=VIDEO_ID,
        at_seconds=300,
        source=CaptureSource.WEB,
        quote="kept",
        quote_start_seconds=300,
    )
    waiting = Moment(
        user_id=user.id,
        video_id="bbbbbbbbbbb",
        at_seconds=5,
        source=CaptureSource.LEGACY,
    )
    imported.updated_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
    db_session.add_all([imported, quoted, waiting])
    db_session.flush()

    class Session:
        def __getattr__(self, name):
            return getattr(db_session, name)

        def close(self):
            pass

    loads = []

    def load(video_id):
        loads.append(video_id)
        return TRANSCRIPT

    monkeypatch.setattr(database, "SessionLocal", Session)
    monkeypatch.setattr(transcripts, "load_transcript", load)

    backfill.backfill_quotes()

    assert loads == [VIDEO_ID]
    assert imported.quote and "leftmost column" in imported.quote
    # Filling a quote is not activity, so the library order stays put.
    db_session.expire(imported)
    assert imported.updated_at == datetime(2026, 1, 2, tzinfo=timezone.utc)
    assert quoted.quote == "kept"
    assert waiting.quote is None


@pytest.mark.parametrize("recompute_all", [False, True])
def test_backfill_existing_quotes_preserves_activity(
    db_session, user, monkeypatch, recompute_all
):
    from src import database
    from src.management import backfill

    db_session.add(
        Video(video_id=VIDEO_ID, title="A", transcript_status=TranscriptStatus.READY)
    )
    db_session.flush()
    original_time = datetime(2026, 1, 2, tzinfo=timezone.utc)
    moments = [
        Moment(
            user_id=user.id,
            video_id=VIDEO_ID,
            at_seconds=at,
            source=CaptureSource.LEGACY,
            quote="old long quote",
            quote_start_seconds=70,
            updated_at=original_time,
        )
        for at in [100, 200]
    ]
    db_session.add_all(moments)
    db_session.commit()

    class Session:
        def __getattr__(self, name):
            return getattr(db_session, name)

        def close(self):
            pass

    loads = []

    def load(video_id):
        loads.append(video_id)
        return TRANSCRIPT

    monkeypatch.setattr(database, "SessionLocal", Session)
    monkeypatch.setattr(transcripts, "load_transcript", load)
    backfill.backfill_quotes(recompute_all=recompute_all)
    db_session.expire_all()

    assert loads == ([VIDEO_ID] if recompute_all else [])
    assert all(moment.updated_at == original_time for moment in moments)
    if recompute_all:
        assert moments[0].quote == (
            "composite index order matters the leftmost column comes first"
        )
        assert moments[0].quote_start_seconds == 95
        assert moments[1].quote is None
        assert moments[1].quote_start_seconds is None
    else:
        assert all(moment.quote == "old long quote" for moment in moments)


@pytest.mark.asyncio
async def test_pending_transcript_returns_conflict_without_charging(
    client, db_session, user
):
    moment, _ = capture(db_session, user, ai=True)
    balance = user.credits_balance
    response = await client.post(
        f"/v2/internal/videos/{VIDEO_ID}/pending-moments", headers=admin_headers()
    )
    assert response.status_code == 409
    db_session.refresh(moment)
    db_session.refresh(user)
    assert moment.ai_status == AiStatus.WAITING_TRANSCRIPT
    assert user.credits_balance == balance
    assert charges(db_session, user) == []

    db_session.query(Video).filter_by(
        video_id=VIDEO_ID
    ).one().transcript_status = TranscriptStatus.READY
    db_session.flush()
    response = await client.post(
        f"/v2/internal/videos/{VIDEO_ID}/pending-moments", headers=admin_headers()
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()["moments"]] == [moment.id]
    assert len(charges(db_session, user)) == 1

    response = await client.post(
        f"/v2/internal/videos/{VIDEO_ID}/pending-moments", headers=admin_headers()
    )
    assert response.status_code == 200
    assert response.json()["moments"] == []
    assert len(charges(db_session, user)) == 1
