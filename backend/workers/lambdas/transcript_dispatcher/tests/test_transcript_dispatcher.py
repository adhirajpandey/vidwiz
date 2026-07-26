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
    monkeypatch.setenv("SQS_AI_SUMMARY_QUEUE_URL", "summary-queue")


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


def test_dispatch_service_uses_domain_specific_queue_urls(monkeypatch):
    dispatch_service = _load_module("dispatch_service.py", monkeypatch)
    calls = []

    class FakeSqs:
        def send_message_batch(self, **kwargs):
            calls.append(kwargs)
            return {"Successful": [{"Id": "0"}]}

        def send_message(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(dispatch_service.boto3, "client", lambda _name: FakeSqs())

    dispatch_service.push_notes_to_sqs_batch([{"id": 1}])
    dispatch_service.push_summary_to_sqs("video-id")

    assert calls[0]["QueueUrl"] == "note-queue"
    assert calls[1]["QueueUrl"] == "summary-queue"


def test_dispatch_service_skips_summary_without_summary_queue(monkeypatch):
    monkeypatch.delenv("SQS_AI_SUMMARY_QUEUE_URL", raising=False)
    dispatch_service = _load_module("dispatch_service.py", monkeypatch)
    dispatch_service.SQS_AI_SUMMARY_QUEUE_URL = None

    assert dispatch_service.push_summary_to_sqs("video-id") is False


def test_fetch_all_notes_uses_configured_request_timeout(monkeypatch):
    monkeypatch.setenv("REQUEST_TIMEOUT", "17")
    dispatch_service = _load_module("dispatch_service.py", monkeypatch)
    calls = []

    class Response:
        status_code = 200
        text = '{"notes":[]}'

        def json(self):
            return {"notes": []}

    monkeypatch.setattr(
        dispatch_service.requests,
        "get",
        lambda *args, **kwargs: calls.append((args, kwargs)) or Response(),
    )

    assert dispatch_service.fetch_all_notes("video-id") == []
    assert calls[0][1]["timeout"] == 17
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

    result = dispatch_service.push_notes_to_sqs_batch(
        [{"id": 1, "text": "private body"}, {"id": 2, "text": "private body"}]
    )

    assert result["sent"] == 1
    assert result["failed"] == 1
    assert any(
        record[2].get("failed") == 1
        for record in dispatch_service.logger.records
    )
    assert "sensitive AWS detail" not in str(dispatch_service.logger.records)
    assert "private body" not in str(dispatch_service.logger.records)


def test_handler_delegates_s3_and_manual_video_ids(monkeypatch):
    handler = _load_module("handler.py", monkeypatch)
    calls = []
    monkeypatch.setattr(
        handler.dispatch_service,
        "dispatch_videos",
        lambda video_ids, dispatch_summary: calls.append((video_ids, dispatch_summary)),
    )
    event = {
        "Records": [{"s3": {"object": {"key": "transcripts/s3-video.json"}}}],
        "video_ids": ["manual-video"],
    }

    handler.lambda_handler(event, object())

    assert calls == [(["s3-video", "manual-video"], True)]
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
