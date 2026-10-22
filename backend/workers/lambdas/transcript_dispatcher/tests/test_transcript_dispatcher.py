from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType
import uuid

import pytest

WORKER_DIR = Path(__file__).resolve().parents[1]


class FakeLogger:
    inject_options = None

    def __init__(self):
        self.records = []

    def _record(self, level, message, kwargs):
        self.records.append((level, message, kwargs.get("extra", {})))

    def info(self, message, **kwargs):
        self._record("info", message, kwargs)

    def error(self, message, **kwargs):
        self._record("error", message, kwargs)

    def exception(self, message, **kwargs):
        self._record("exception", message, kwargs)

    def inject_lambda_context(self, **kwargs):
        FakeLogger.inject_options = kwargs
        return lambda function: function


def _install_powertools_stub(monkeypatch):
    FakeLogger.inject_options = None
    powertools = ModuleType("aws_lambda_powertools")
    powertools.Logger = FakeLogger
    monkeypatch.setitem(sys.modules, "aws_lambda_powertools", powertools)


def _set_environment(monkeypatch):
    monkeypatch.setenv("VIDWIZ_INTERNAL_API_BASE_URL", "https://internal.example")
    monkeypatch.setenv("VIDWIZ_INTERNAL_API_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("SQS_AI_NOTE_QUEUE_URL", "note-queue")


def _load_module(filename, monkeypatch):
    _install_powertools_stub(monkeypatch)
    _set_environment(monkeypatch)
    monkeypatch.syspath_prepend(str(WORKER_DIR))
    module_name = f"test_dispatcher_{filename.removesuffix('.py')}_{uuid.uuid4().hex}"
    spec = spec_from_file_location(module_name, WORKER_DIR / filename)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dispatch_videos_queues_only_ai_lines(monkeypatch):
    dispatch_service = _load_module("dispatch_service.py", monkeypatch)
    calls = []

    class FakeSqs:
        def send_message_batch(self, **kwargs):
            calls.append(kwargs)
            return {"Successful": [{"Id": "0"}]}

    monkeypatch.setattr(dispatch_service.boto3, "client", lambda _name: FakeSqs())
    monkeypatch.setattr(
        dispatch_service, "collect_pending_moments", lambda _video_id: [{"id": 1}]
    )

    dispatch_service.dispatch_videos(["video-id"])

    # The API queues overviews when it stores the transcript.
    assert [call["QueueUrl"] for call in calls] == ["note-queue"]
    assert not hasattr(dispatch_service, "push_summary_to_sqs")


def test_collect_pending_moments_preserves_configured_read_timeout(monkeypatch):
    """Allow slow successful responses while bounding connection setup."""
    monkeypatch.setenv("REQUEST_TIMEOUT", "17")
    dispatch_service = _load_module("dispatch_service.py", monkeypatch)
    calls = []

    class Response:
        status_code = 200
        text = '{"moments":[]}'

        def json(self):
            return {"moments": []}

    monkeypatch.setattr(
        dispatch_service.requests,
        "post",
        lambda *args, **kwargs: calls.append((args, kwargs)) or Response(),
    )

    assert dispatch_service.collect_pending_moments("video-id") == []
    assert calls[0][0][0].endswith("/v2/internal/videos/video-id/pending-moments")
    assert calls[0][1]["timeout"] == (1, 17)
    assert "response_preview" not in dispatch_service.logger.records[0][2]


def test_sqs_partial_failure_log_excludes_message_and_body(monkeypatch):
    dispatch_service = _load_module("dispatch_service.py", monkeypatch)

    class FakeSqs:
        def send_message_batch(self, **_kwargs):
            return {
                "Successful": [{"Id": "0"}],
                "Failed": [
                    {
                        "Id": "1",
                        "Code": "InternalError",
                        "SenderFault": False,
                        "Message": "sensitive AWS detail",
                    }
                ],
            }

    monkeypatch.setattr(dispatch_service.boto3, "client", lambda _name: FakeSqs())

    result = dispatch_service.push_moments_to_sqs_batch(
        [{"id": 1, "text": "private body"}, {"id": 2, "text": "private body"}]
    )

    assert result["sent"] == 1
    assert result["failed"] == 1
    assert any(
        record[2].get("failed") == 1 for record in dispatch_service.logger.records
    )
    assert "sensitive AWS detail" not in str(dispatch_service.logger.records)
    assert "private body" not in str(dispatch_service.logger.records)


def test_handler_delegates_s3_and_manual_video_ids(monkeypatch):
    handler = _load_module("handler.py", monkeypatch)
    calls = []
    monkeypatch.setattr(
        handler.dispatch_service,
        "dispatch_videos",
        lambda video_ids: calls.append(video_ids),
    )
    event = {
        "Records": [{"s3": {"object": {"key": "transcripts/s3-video.json"}}}],
        "video_ids": ["manual-video"],
    }

    handler.lambda_handler(event, object())

    assert calls == [["s3-video", "manual-video"]]
    assert FakeLogger.inject_options == {"log_event": False}


def test_handler_reraises_dispatch_failure(monkeypatch):
    handler = _load_module("handler.py", monkeypatch)
    monkeypatch.setattr(
        handler.dispatch_service,
        "dispatch_videos",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("dispatch failed")),
    )

    with pytest.raises(RuntimeError, match="dispatch failed"):
        handler.lambda_handler({"video_ids": ["video-id"]}, object())


@pytest.mark.parametrize("conflicts", [1, 2, 4])
def test_pending_moments_retries_until_ready(monkeypatch, conflicts):
    """Readiness conflicts back off before returning the jobs unchanged."""
    service = _load_module("dispatch_service.py", monkeypatch)
    sleeps = []
    statuses = iter([409] * conflicts + [200])
    jobs = [{"id": 1}]

    class Response:
        def __init__(self):
            self.status_code = next(statuses)

        def json(self):
            return {"moments": jobs}

    monkeypatch.setattr(service.requests, "post", lambda *_a, **_k: Response())
    monkeypatch.setattr(service.time, "sleep", sleeps.append)
    assert service.collect_pending_moments("video-id") == jobs
    assert sleeps == [1, 2, 4, 8][:conflicts]


def test_exhausted_readiness_retries_fail_invocation(monkeypatch):
    """Persistent conflicts must escape the handler for AWS to retry."""
    handler = _load_module("handler.py", monkeypatch)
    service = handler.dispatch_service
    calls = []
    sleeps = []

    class Response:
        status_code = 409

    monkeypatch.setattr(
        service.requests,
        "post",
        lambda *_a, **_k: calls.append(1) or Response(),
    )
    monkeypatch.setattr(service.time, "sleep", sleeps.append)
    with pytest.raises(RuntimeError, match="Transcript is not ready"):
        handler.lambda_handler({"video_ids": ["video-id"]}, object())
    assert len(calls) == 5
    assert sleeps == [1, 2, 4, 8]


def test_other_http_errors_fail_for_lambda_retry_without_sleep(monkeypatch):
    """Only readiness conflicts use the local backoff loop."""
    service = _load_module("dispatch_service.py", monkeypatch)
    sleeps = []

    class Response:
        status_code = 500

    monkeypatch.setattr(service.requests, "post", lambda *_a, **_k: Response())
    monkeypatch.setattr(service.time, "sleep", sleeps.append)
    with pytest.raises(RuntimeError, match="Failed to collect pending moments"):
        service.collect_pending_moments("video-id")
    assert sleeps == []


def test_read_timeout_fails_invocation_and_next_delivery_sends_jobs(monkeypatch):
    """A lost collection response triggers Lambda retry instead of silent success."""
    handler = _load_module("handler.py", monkeypatch)
    service = handler.dispatch_service
    sends = []

    def timeout(*_args, **_kwargs):
        raise service.requests.exceptions.ReadTimeout("private request details")

    monkeypatch.setattr(service.requests, "post", timeout)
    monkeypatch.setattr(
        service,
        "push_moments_to_sqs_batch",
        lambda jobs: sends.append(jobs) or {"sent": len(jobs), "failed": 0},
    )
    with pytest.raises(RuntimeError, match="Failed to collect pending moments"):
        handler.lambda_handler({"video_ids": ["video-id"]}, object())
    assert sends == []
    assert "private request details" not in str(service.logger.records)

    class Response:
        status_code = 200

        def json(self):
            return {"moments": [{"id": 1}]}

    monkeypatch.setattr(service.requests, "post", lambda *_a, **_k: Response())
    handler.lambda_handler({"video_ids": ["video-id"]}, object())
    assert sends == [[{"id": 1}]]


@pytest.mark.parametrize("raises", [False, True])
def test_sqs_failure_fails_invocation(monkeypatch, raises):
    """Partial and complete send failures must both trigger Lambda retry."""
    handler = _load_module("handler.py", monkeypatch)
    service = handler.dispatch_service
    monkeypatch.setattr(service, "collect_pending_moments", lambda _id: [{"id": 1}])

    class Sqs:
        def send_message_batch(self, **_kwargs):
            if raises:
                raise RuntimeError("SQS is unavailable")
            return {"Failed": [{"Id": "0"}]}

    monkeypatch.setattr(service.boto3, "client", lambda _name: Sqs())
    with pytest.raises(RuntimeError, match="Failed to send AI moments"):
        handler.lambda_handler({"video_ids": ["video-id"]}, object())
