"""Bounded application metrics and periodically refreshed database snapshots."""

from __future__ import annotations

import contextvars
import logging
import re
import time
from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import Depends, FastAPI
from prometheus_client import (
    CollectorRegistry,
    Counter,
    GCCollector,
    Gauge,
    Histogram,
    PlatformCollector,
    ProcessCollector,
)
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from src.internal.dependencies import require_admin_token

logger = logging.getLogger(__name__)
METRICS_REFRESH_SECONDS = 60
METRICS_QUERY_TIMEOUT_SECONDS = 10
_current: contextvars.ContextVar["Metrics | None"] = contextvars.ContextVar(
    "vidwiz_metrics", default=None
)

WORKFLOWS = (
    "title_resolution",
    "metadata",
    "transcript",
    "ai_moment",
    "overview",
    "wiz_chat",
)
WORKFLOW_STATES = {
    "title_resolution": ("resolving", "awaiting_user", "failed"),
    "metadata": ("pending", "in_progress", "failed"),
    "transcript": ("pending",),
    "ai_moment": ("waiting_transcript", "queued", "failed"),
    "overview": ("pending", "queued", "failed"),
}
EVENTS = (
    "task_queued",
    "task_claimed",
    "task_retrying",
    "task_completed",
    "task_failed",
    "title_candidates_offered",
    "title_resolved",
    "title_failed",
    "transcript_ready",
    "transcript_unavailable",
    "overview_queued",
    "overview_ready",
    "overview_failed",
    "ai_queued",
    "ai_ready",
    "ai_failed",
    "ai_waiting_transcript",
    "ai_insufficient_credits",
    "ai_no_transcript",
    "wiz_processing",
    "wiz_completed",
    "wiz_failed",
    "wiz_interrupted",
)
WIZ_SCOPES = ("video", "library")
WIZ_OUTCOMES = ("completed", "failed", "interrupted")

# Only valid workflow/event/reason combinations are initialized. This makes a
# zero count distinct from an absent metric family without emitting a Cartesian
# product of unrelated labels.
EVENT_SERIES = {
    (workflow, event, reason)
    for workflow in ("title_resolution", "metadata", "transcript")
    for event, reason in (
        ("task_queued", "none"),
        ("task_claimed", "none"),
        ("task_retrying", "retry"),
        ("task_completed", "none"),
        ("task_failed", "worker_error"),
    )
}
EVENT_SERIES.update(
    {
        ("title_resolution", "title_candidates_offered", "none"),
        ("title_resolution", "title_resolved", "none"),
        ("title_resolution", "title_failed", "title_unresolved"),
        ("transcript", "transcript_ready", "none"),
        ("transcript", "transcript_unavailable", "worker_error"),
        ("transcript", "transcript_unavailable", "no_transcript"),
        ("overview", "overview_queued", "none"),
        ("overview", "overview_ready", "none"),
        ("overview", "overview_failed", "queue_error"),
        ("overview", "overview_failed", "worker_error"),
        ("overview", "overview_failed", "stale"),
        ("ai_moment", "ai_queued", "none"),
        ("ai_moment", "ai_ready", "none"),
        ("ai_moment", "ai_failed", "queue_error"),
        ("ai_moment", "ai_failed", "worker_error"),
        ("ai_moment", "ai_failed", "title_unresolved"),
        ("ai_moment", "ai_failed", "stale"),
        ("ai_moment", "ai_waiting_transcript", "none"),
        ("ai_moment", "ai_insufficient_credits", "insufficient_credits"),
        ("ai_moment", "ai_no_transcript", "no_transcript"),
        ("wiz_chat", "wiz_processing", "none"),
        ("wiz_chat", "wiz_completed", "none"),
        ("wiz_chat", "wiz_failed", "model_error"),
        ("wiz_chat", "wiz_failed", "invalid_output"),
        ("wiz_chat", "wiz_failed", "empty_response"),
        ("wiz_chat", "wiz_interrupted", "interrupted"),
    }
)


class Metrics:
    """One registry per app instance so repeated app factories stay test-safe."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        GCCollector(registry=self.registry)
        PlatformCollector(registry=self.registry)
        ProcessCollector(registry=self.registry)
        self.backlog = Gauge(
            "vidwiz_workflow_backlog",
            "Current workflow records by state.",
            ("workflow", "state"),
            registry=self.registry,
        )
        self.oldest_age = Gauge(
            "vidwiz_workflow_oldest_age_seconds",
            "Age of the oldest workflow record in a state.",
            ("workflow", "state"),
            registry=self.registry,
        )
        self.events = Counter(
            "vidwiz_workflow_events_total",
            "Committed workflow transitions.",
            ("workflow", "event", "reason"),
            registry=self.registry,
        )
        for labels in EVENT_SERIES:
            self.events.labels(*labels)
        self.wiz_duration = Histogram(
            "vidwiz_wiz_stream_duration_seconds",
            "End-to-end Wiz response stream duration.",
            ("scope", "outcome"),
            buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120, 300),
            registry=self.registry,
        )
        for scope in WIZ_SCOPES:
            for outcome in WIZ_OUTCOMES:
                self.wiz_duration.labels(scope, outcome)
        self.database_ready = Gauge(
            "vidwiz_database_ready",
            "Database status: -1 unknown, 0 unavailable, 1 ready.",
            registry=self.registry,
        )
        self.snapshot_success = Gauge(
            "vidwiz_metrics_snapshot_success",
            "Whether the latest DB snapshot succeeded.",
            registry=self.registry,
        )
        self.snapshot_timestamp = Gauge(
            "vidwiz_metrics_snapshot_timestamp_seconds",
            "Unix time of the last successful DB snapshot.",
            registry=self.registry,
        )
        self._database_checked_at: float | None = None
        self.database_ready.set(-1)
        self.snapshot_success.set(-1)
        self.snapshot_timestamp.set(float("nan"))
        for workflow, states in WORKFLOW_STATES.items():
            for state in states:
                self.backlog.labels(workflow, state).set(float("nan"))
                self.oldest_age.labels(workflow, state).set(float("nan"))

    def event(
        self, workflow: str, event: str, reason: str = "none", amount: int = 1
    ) -> None:
        # Drop unknown values rather than introducing unbounded label cardinality.
        if workflow not in WORKFLOWS or event not in EVENTS:
            return
        if (workflow, event, reason) not in EVENT_SERIES:
            if (workflow, event, "worker_error") in EVENT_SERIES:
                reason = "worker_error"
            else:
                return
        if amount > 0:
            self.events.labels(workflow, event, reason).inc(amount)

    def observe_wiz(self, scope: str, outcome: str, duration: float) -> None:
        if scope in WIZ_SCOPES and outcome in WIZ_OUTCOMES:
            self.wiz_duration.labels(scope, outcome).observe(max(0, duration))

    def is_database_ready(self) -> bool:
        return (
            self.database_ready._value.get() == 1
            and self._database_checked_at is not None
            and time.monotonic() - self._database_checked_at < 120
        )

    def failed_snapshot(self) -> None:
        # Keep last-known aggregate values and timestamp; expose freshness/failure separately.
        self.snapshot_success.set(0)

    def collect_snapshot(self, session_factory: Callable):
        """Run a small set of grouped DB reads; callers bound the background wait."""
        from src.internal.constants import (
            FETCH_METADATA_TASK_TYPE,
        )
        from src.internal.models import Task, TaskStatus
        from src.moments.models import AiStatus, Moment, ResolveStatus
        from src.videos.models import OverviewStatus, TranscriptStatus, Video

        db = None
        connectivity_checked = False
        snapshot: dict[tuple[str, str], tuple[int, float]] = {}
        try:
            db = session_factory()
            db.execute(text("SET LOCAL statement_timeout = '5s'"))
            db.execute(select(1)).scalar_one()
            connectivity_checked = True
            self.database_ready.set(1)
            self._database_checked_at = time.monotonic()
            now = datetime.now(timezone.utc)

            def stage_rows(workflow, rows, states):
                by_state = {
                    state: (int(count), oldest) for state, count, oldest in rows
                }
                for state in states:
                    count, oldest = by_state.get(state, (0, None))
                    age = 0
                    if oldest is not None:
                        if oldest.tzinfo is None:
                            oldest = oldest.replace(tzinfo=timezone.utc)
                        age = max(0, (now - oldest).total_seconds())
                    snapshot[(workflow, state)] = (count, age)

            task_types = {
                "metadata": FETCH_METADATA_TASK_TYPE,
            }
            for workflow, task_type in task_types.items():
                rows = db.execute(
                    select(
                        Task.status,
                        func.count(Task.id),
                        func.min(func.coalesce(Task.started_at, Task.created_at)),
                    )
                    .where(
                        Task.task_type == task_type,
                        Task.status.in_(
                            (
                                TaskStatus.PENDING,
                                TaskStatus.IN_PROGRESS,
                                TaskStatus.FAILED,
                            )
                        ),
                    )
                    .group_by(Task.status)
                ).all()
                stage_rows(
                    workflow,
                    [(row[0].value, row[1], row[2]) for row in rows],
                    WORKFLOW_STATES[workflow],
                )

            title_rows = db.execute(
                select(
                    Moment.resolve_status,
                    func.count(Moment.id),
                    func.min(Moment.created_at),
                )
                .where(
                    Moment.resolve_status.in_(
                        (ResolveStatus.RESOLVING, ResolveStatus.UNRESOLVED)
                    )
                )
                .group_by(Moment.resolve_status)
            ).all()
            title_values = []
            for status, count, oldest in title_rows:
                if status == ResolveStatus.RESOLVING:
                    title_values.append(("resolving", count, oldest))
                else:
                    candidates = db.execute(
                        select(
                            func.count(Moment.id), func.min(Moment.created_at)
                        ).where(
                            Moment.resolve_status == ResolveStatus.UNRESOLVED,
                            Moment.resolve_candidates.is_not(None),
                        )
                    ).one()
                    failed = db.execute(
                        select(
                            func.count(Moment.id), func.min(Moment.created_at)
                        ).where(
                            Moment.resolve_status == ResolveStatus.UNRESOLVED,
                            Moment.resolve_candidates.is_(None),
                        )
                    ).one()
                    title_values.extend(
                        (
                            ("awaiting_user", candidates[0], candidates[1]),
                            ("failed", failed[0], failed[1]),
                        )
                    )
            stage_rows(
                "title_resolution", title_values, WORKFLOW_STATES["title_resolution"]
            )

            ai_rows = db.execute(
                select(
                    Moment.ai_status, func.count(Moment.id), func.min(Moment.created_at)
                )
                .where(
                    Moment.ai_status.in_(
                        (AiStatus.WAITING_TRANSCRIPT, AiStatus.QUEUED, AiStatus.FAILED)
                    )
                )
                .group_by(Moment.ai_status)
            ).all()
            stage_rows(
                "ai_moment",
                [(status.value, count, oldest) for status, count, oldest in ai_rows],
                WORKFLOW_STATES["ai_moment"],
            )

            transcript_rows = db.execute(
                select(
                    Video.transcript_status,
                    func.count(Video.id),
                    func.min(Video.updated_at),
                )
                .where(Video.transcript_status == TranscriptStatus.PENDING)
                .group_by(Video.transcript_status)
            ).all()
            stage_rows(
                "transcript",
                [
                    (status.value, count, oldest)
                    for status, count, oldest in transcript_rows
                ],
                WORKFLOW_STATES["transcript"],
            )

            overview_rows = db.execute(
                select(
                    Video.overview_status,
                    func.count(Video.id),
                    func.min(Video.overview_status_at),
                )
                .where(
                    Video.overview_status.in_(
                        (
                            OverviewStatus.PENDING,
                            OverviewStatus.QUEUED,
                            OverviewStatus.FAILED,
                        )
                    )
                )
                .group_by(Video.overview_status)
            ).all()
            stage_rows(
                "overview",
                [
                    (status.value, count, oldest)
                    for status, count, oldest in overview_rows
                ],
                WORKFLOW_STATES["overview"],
            )
            db.commit()
            # Dashboard queries gate on this gauge while the cached series update.
            self.snapshot_success.set(0)
            for (workflow, state), (count, age) in snapshot.items():
                self.backlog.labels(workflow, state).set(count)
                self.oldest_age.labels(workflow, state).set(age)
            self.database_ready.set(1)
            self.snapshot_timestamp.set(now.timestamp())
            self.snapshot_success.set(1)
        except Exception as exc:
            if not connectivity_checked or (
                isinstance(exc, DBAPIError) and exc.connection_invalidated
            ):
                self.database_ready.set(0)
            self.failed_snapshot()
            if db is not None:
                try:
                    db.rollback()
                except Exception:
                    self.database_ready.set(0)
            logger.error(
                "Workflow metrics snapshot failed",
                extra={"error_type": type(exc).__name__},
            )
        finally:
            if db is not None:
                db.close()


def record_workflow_event(
    workflow: str, event: str, reason: str = "none", amount: int = 1
) -> None:
    metrics = _current.get()
    if metrics is not None:
        metrics.event(workflow, event, reason, amount)


def current_metrics() -> Metrics | None:
    return _current.get()


def bind_metrics(metrics: Metrics | None):
    return _current.set(metrics)


def unbind_metrics(token) -> None:
    _current.reset(token)


def init_metrics(app: FastAPI) -> Metrics:
    metrics = Metrics()
    app.state.metrics = metrics
    instrumentator = Instrumentator(
        registry=metrics.registry,
        should_group_status_codes=True,
        should_exclude_streaming_duration=True,
        # Instrumentator 8.x creates this gauge in the global registry.
        should_instrument_requests_inprogress=False,
    ).instrument(
        app,
        latency_highr_buckets=(0.1, 0.3, 0.5, 1, 2.5, 5, 10, 30, 60, 120, 300),
        latency_lowr_buckets=(0.1, 0.5, 1, 5, 30),
    )
    instrumentator.expose(
        app,
        endpoint="/v2/internal/metrics",
        include_in_schema=False,
        dependencies=[Depends(require_admin_token)],
    )
    return metrics


def correlation_id_from_header(value: str | None) -> str | None:
    value = (value or "").strip()
    if len(value) <= 128 and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", value):
        return value
    return None
