from datetime import datetime, timezone

import pytest

from src.internal.models import Task, TaskStatus
from src.metrics import Metrics
from src.videos.models import Video, TranscriptStatus
from src.llm_budget import Budget, check_batch_budget, next_reset, read_budget


def test_snapshot_counts_latest_attempts_and_keeps_unknown_failures(db_session):
    for index in range(6):
        db_session.add(
            Video(
                video_id=f"health{index:05}",
                transcript_status=TranscriptStatus.READY,
                video_metadata={"title": "ready"} if index == 0 else None,
            )
        )
    db_session.flush()

    def task(index, status, **details):
        db_session.add(
            Task(
                task_type="fetch_metadata",
                status=status,
                task_details={"video_id": f"health{index:05}"},
                worker_details=details,
            )
        )
        db_session.flush()

    task(0, TaskStatus.FAILED, error_message="unknown")  # content wins
    task(1, TaskStatus.FAILED, error_message="unknown")
    task(1, TaskStatus.COMPLETED)  # later success wins
    task(2, TaskStatus.FAILED, error_message="Private video")
    task(2, TaskStatus.FAILED, error_message="Private video")  # one item
    task(
        3,
        TaskStatus.FAILED,
        error_kind="youtube_blocked",
        error_message="Video unavailable",
    )
    task(4, TaskStatus.FAILED, error_kind="not_found")  # ambiguous old kind
    task(5, TaskStatus.FAILED, error_message="unknown")
    task(5, TaskStatus.PENDING)  # active retry wins
    metrics = Metrics()
    metrics.collect_snapshot(lambda: db_session)
    assert metrics.snapshot_success._value.get() == 1
    assert metrics.backlog.labels("metadata", "failed")._value.get() == 2
    assert metrics.backlog.labels("metadata", "unavailable")._value.get() == 1
    assert metrics.backlog.labels("metadata", "pending")._value.get() == 1


def test_transcript_block_is_not_unavailable_content(db_session):
    for index, kind in enumerate(["youtube_blocked", "no_transcript", "unavailable"]):
        video_id = f"health{index:05}"
        db_session.add(
            Video(video_id=video_id, transcript_status=TranscriptStatus.UNAVAILABLE)
        )
        db_session.add(
            Task(
                task_type="fetch_transcript",
                status=TaskStatus.FAILED,
                task_details={"video_id": video_id},
                worker_details={"error_kind": kind},
            )
        )
    db_session.flush()
    metrics = Metrics()
    metrics.collect_snapshot(lambda: db_session)
    assert metrics.snapshot_success._value.get() == 1
    assert metrics.backlog.labels("transcript", "failed")._value.get() == 1
    assert metrics.backlog.labels("transcript", "unavailable")._value.get() == 2


@pytest.mark.parametrize(
    "period, expected",
    [
        ("daily", "2026-11-15T00:00:00+00:00"),
        ("weekly", "2026-11-16T00:00:00+00:00"),
        ("monthly", "2026-12-01T00:00:00+00:00"),
    ],
)
def test_budget_reset_uses_utc_calendar(period, expected):
    now = datetime(2026, 11, 14, 12, 40, tzinfo=timezone.utc)
    assert next_reset(period, now) == datetime.fromisoformat(expected).timestamp()
    assert next_reset("unknown", now) is None
    assert next_reset(None, now) is None


def test_batch_budget_rejects_unknown_and_preserves_reserve():
    assert check_batch_budget(Budget(5, 1, None, 0, 1), 10, 0.01, 0.5) == 0.1
    with pytest.raises(ValueError, match="reserve"):
        check_batch_budget(Budget(5, 1, None, 0, 1), 60, 0.01, 0.5)
    with pytest.raises(ValueError, match="unknown"):
        check_batch_budget(Budget(None, None, None, 0, None), 1, 0.01, 0.5)
    with pytest.raises(ValueError):
        check_batch_budget(Budget(5, 1, None, 0, 1), 1, float("nan"), 0.5)


def test_malformed_budget_cannot_look_fresh_or_unlimited(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(
        "requests.get",
        lambda *a, **k: SimpleNamespace(
            raise_for_status=lambda: None, json=lambda: {"data": {}}
        ),
    )
    with pytest.raises(KeyError):
        read_budget("test", "https://example.test")


def test_effective_budget_limits_batch_headroom(monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(
        "requests.get",
        lambda *a, **k: SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {
                "data": {
                    "limit": 5,
                    "limit_remaining": 4,
                    "limit_reset": "weekly",
                    "effective_budget": {"remaining_usd": 0.25},
                }
            },
        ),
    )
    budget = read_budget("test", "https://example.test")
    assert budget.remaining == 4
    assert budget.available == 0.25
    with pytest.raises(ValueError):
        check_batch_budget(budget, 1, 0.1, 0.2)


def test_legacy_unavailable_without_attempt_is_unknown(db_session):
    db_session.add(
        Video(video_id="health00000", transcript_status=TranscriptStatus.UNAVAILABLE)
    )
    db_session.flush()
    metrics = Metrics()
    metrics.collect_snapshot(lambda: db_session)
    assert metrics.snapshot_success._value.get() == 1
    assert metrics.backlog.labels("transcript", "unknown")._value.get() == 1
    assert metrics.backlog.labels("transcript", "failed")._value.get() == 0


def test_user_choices_remain_separate_and_do_not_expire(db_session, user):
    from src.moments.models import Moment, AiStatus, ResolveStatus, CaptureSource
    from datetime import timedelta

    for candidates in ([{"video_id": "health00000"}], []):
        db_session.add(
            Moment(
                user_id=user.id,
                at_seconds=60,
                source=CaptureSource.PHONE,
                resolve_status=ResolveStatus.UNRESOLVED,
                resolve_candidates=candidates,
                ai_status=AiStatus.WAITING_TRANSCRIPT,
                created_at=datetime.now(timezone.utc) - timedelta(days=100),
            )
        )
    db_session.flush()
    metrics = Metrics()
    metrics.collect_snapshot(lambda: db_session)
    assert metrics.snapshot_success._value.get() == 1
    assert metrics.backlog.labels("title_resolution", "awaiting_user")._value.get() == 1
    assert metrics.backlog.labels("title_resolution", "failed")._value.get() == 1
    assert metrics.backlog.labels("ai_moment", "waiting_title")._value.get() == 2
    assert metrics.backlog.labels("ai_moment", "waiting_transcript")._value.get() == 0


def test_overview_batch_dry_run_and_budget_failure_never_queue(monkeypatch):
    from types import SimpleNamespace
    from src.management import backfill

    calls = []
    monkeypatch.setattr(
        backfill.database, "SessionLocal", lambda: SimpleNamespace(close=lambda: None)
    )
    monkeypatch.setattr(
        backfill.overview,
        "backfill_candidates",
        lambda *args: [SimpleNamespace(video_id="abc")],
    )
    monkeypatch.setattr(
        backfill.overview, "queue", lambda *args: calls.append("queued")
    )
    monkeypatch.setattr(backfill, "read_budget", lambda *args: Budget(5, 1, None, 0, 1))
    backfill.backfill_overviews(1, 0.01, 0.5)
    assert not calls
    with pytest.raises(ValueError, match="reserve"):
        backfill.backfill_overviews(1, 1, 0.5, apply=True)
    assert not calls
