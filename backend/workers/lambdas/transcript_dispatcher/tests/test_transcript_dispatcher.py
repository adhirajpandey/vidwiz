from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType
import uuid

WORKER_DIR = Path(__file__).resolve().parents[1]


class FakeLogger:
    def info(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass

    def warning(self, *_args, **_kwargs):
        pass

    def inject_lambda_context(self, **_kwargs):
        return lambda function: function


def _install_powertools_stub(monkeypatch):
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
