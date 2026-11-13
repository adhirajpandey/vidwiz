import json
import logging
import asyncio
import threading

from prometheus_client import generate_latest
from prometheus_client.parser import text_string_to_metric_families
import pytest

from src.logging import (
    JsonFormatter,
    RequestIdFilter,
    correlation_id_var,
    request_id_var,
)
from src import main as main_module
from src.main import create_app
from src.metrics import Metrics, correlation_id_from_header


def test_each_app_factory_uses_an_isolated_registry():
    first = create_app().state.metrics
    second = create_app().state.metrics

    assert first is not second
    assert first.registry is not second.registry
    assert b"vidwiz_workflow_backlog" in generate_latest(first.registry)
    assert b"vidwiz_workflow_backlog" in generate_latest(second.registry)
    output = generate_latest(first.registry)
    assert b"process_cpu_seconds_total" in output
    assert b"python_gc_objects_collected_total" in output
    assert b"python_info" in output


def test_snapshot_aggregates_start_unknown_and_failure_keeps_last_values():
    from src.internal.models import TaskStatus

    metrics = Metrics()
    backlog = metrics.backlog.labels("metadata", "pending")
    age = metrics.oldest_age.labels("metadata", "pending")
    assert str(backlog._value.get()) == "nan"
    assert str(age._value.get()) == "nan"
    assert metrics.snapshot_success._value.get() == -1
    assert str(metrics.snapshot_timestamp._value.get()) == "nan"
    assert metrics.database_ready._value.get() == -1

    backlog.set(7)
    age.set(12.5)
    metrics.snapshot_timestamp.set(1234)

    class BrokenAggregateSession:
        def __init__(self):
            self.calls = 0

        def execute(self, statement):
            self.calls += 1
            if self.calls == 2:  # SELECT 1 proves connectivity.
                return type("Result", (), {"scalar_one": lambda _self: 1})()
            if self.calls == 1:  # SET LOCAL statement timeout.
                return None
            if self.calls == 3:  # A successful query is staged, not published.
                return type(
                    "Result",
                    (),
                    {"all": lambda _self: [(TaskStatus.PENDING, 2, None)]},
                )()
            raise RuntimeError("aggregate query failed")

        def commit(self):
            pass

        def rollback(self):
            pass

        def close(self):
            pass

    metrics.collect_snapshot(BrokenAggregateSession)

    assert metrics.database_ready._value.get() == 1
    assert metrics.snapshot_success._value.get() == 0
    assert metrics.snapshot_timestamp._value.get() == 1234
    assert backlog._value.get() == 7
    assert age._value.get() == 12.5


def test_failed_connectivity_check_marks_database_unready():
    metrics = Metrics()

    class UnavailableSession:
        def execute(self, _statement):
            raise ConnectionError("database unavailable")

        def rollback(self):
            pass

        def close(self):
            pass

    metrics.collect_snapshot(UnavailableSession)

    assert metrics.database_ready._value.get() == 0
    assert metrics.snapshot_success._value.get() == 0
    assert str(metrics.backlog.labels("metadata", "pending")._value.get()) == "nan"


def test_successful_snapshot_publishes_ready_empty_backlogs(db_session):
    metrics = Metrics()
    metrics.collect_snapshot(lambda: db_session)

    assert metrics.database_ready._value.get() == 1
    assert metrics.snapshot_success._value.get() == 1
    assert metrics.snapshot_timestamp._value.get() > 0
    for states in metrics.backlog._metrics.values():
        assert states._value.get() == 0


def test_event_labels_are_initialized_bounded_and_wiz_has_no_persisted_backlog():
    metrics = Metrics()
    metrics.event("metadata", "task_failed", "untrusted-value")
    metrics.event("untrusted-workflow", "untrusted-event", "untrusted-value")
    output = generate_latest(metrics.registry).decode()
    samples = [
        sample
        for family in text_string_to_metric_families(output)
        for sample in family.samples
        if sample.name == "vidwiz_workflow_events_total"
    ]
    failed = next(
        sample
        for sample in samples
        if sample.labels
        == {
            "workflow": "metadata",
            "event": "task_failed",
            "reason": "worker_error",
        }
    )
    idle = next(
        sample
        for sample in samples
        if sample.labels
        == {"workflow": "metadata", "event": "task_completed", "reason": "none"}
    )
    assert failed.value == 1
    assert idle.value == 0
    assert "untrusted-value" not in output
    assert 'workflow="wiz_chat",state=' not in output


def test_correlation_is_captured_before_queue_logging_changes_threads():
    request_token = request_id_var.set("request-123")
    correlation_token = correlation_id_var.set("trace:abc-123")
    try:
        record = logging.LogRecord(
            "vidwiz.test", logging.INFO, __file__, 1, "test", (), None
        )
        RequestIdFilter().filter(record)
    finally:
        correlation_id_var.reset(correlation_token)
        request_id_var.reset(request_token)

    payload = json.loads(JsonFormatter().format(record))
    assert payload["request_id"] == "request-123"
    assert payload["correlation_id"] == "trace:abc-123"


def test_correlation_header_is_sanitized_and_bounded():
    assert correlation_id_from_header(" trace:abc-123 ") == "trace:abc-123"
    assert correlation_id_from_header("bad value") is None
    assert correlation_id_from_header("x" * 129) is None


@pytest.mark.asyncio
async def test_correlation_header_is_echoed_and_invalid_values_are_replaced(client):
    supplied = await client.get(
        "/health", headers={"X-Correlation-ID": "trace:abc-123"}
    )
    assert supplied.headers["x-correlation-id"] == "trace:abc-123"

    invalid = await client.get("/health", headers={"X-Correlation-ID": "bad value"})
    replacement = invalid.headers["x-correlation-id"]
    assert replacement.isascii()
    assert replacement.replace("-", "").isalnum()


@pytest.mark.asyncio
async def test_http_latency_is_exposed_in_the_app_registry(client, app):
    response = await client.get("/health")
    assert response.status_code == 200

    samples = [
        sample
        for family in text_string_to_metric_families(
            generate_latest(app.state.metrics.registry).decode()
        )
        for sample in family.samples
    ]
    latency_buckets = [
        sample
        for sample in samples
        if sample.name == "http_request_duration_seconds_bucket"
    ]
    assert latency_buckets
    assert any(
        sample.labels.get("handler") == "/health"
        and sample.labels.get("method") == "GET"
        for sample in latency_buckets
    )
    assert any(
        sample.name == "http_requests_total"
        and sample.labels.get("handler") == "/health"
        and sample.labels.get("method") == "GET"
        and sample.labels.get("status") == "2xx"
        for sample in samples
    )


@pytest.mark.asyncio
async def test_snapshot_loop_does_not_abandon_or_overlap_timed_out_thread(monkeypatch):
    monkeypatch.setattr(main_module, "METRICS_QUERY_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(main_module, "METRICS_REFRESH_SECONDS", 0.01)
    entered = threading.Event()
    release = threading.Event()

    class SlowMetrics:
        calls = 0

        def collect_snapshot(self, _session_factory):
            self.calls += 1
            entered.set()
            release.wait(timeout=2)

        def failed_snapshot(self):
            pass

    metrics = SlowMetrics()
    loop = asyncio.create_task(main_module._metrics_snapshot_loop(metrics, object()))
    assert await asyncio.to_thread(entered.wait, 1)
    await asyncio.sleep(0.05)
    assert metrics.calls == 1

    loop.cancel()
    await asyncio.sleep(0.01)
    assert not loop.done()
    release.set()
    try:
        await loop
    except asyncio.CancelledError:
        pass
    assert metrics.calls == 1


def test_database_readiness_expires_and_histograms_exist_before_chat():
    import time

    metrics = Metrics()
    assert not metrics.is_database_ready()
    metrics.database_ready.set(1)
    metrics._database_checked_at = time.monotonic()
    assert metrics.is_database_ready()
    metrics._database_checked_at -= 121
    assert not metrics.is_database_ready()
    assert b"vidwiz_wiz_stream_duration_seconds_bucket" in generate_latest(metrics.registry)


def test_failed_probe_with_failed_rollback_cannot_leave_readiness_green():
    metrics = Metrics()
    metrics.database_ready.set(1)

    class BrokenSession:
        def execute(self, statement):
            raise ConnectionError("unavailable")

        def rollback(self):
            raise ConnectionError("rollback unavailable")

        def close(self):
            pass

    metrics.collect_snapshot(BrokenSession)
    assert metrics.database_ready._value.get() == 0
    assert metrics.snapshot_success._value.get() == 0
    assert not metrics.is_database_ready()
