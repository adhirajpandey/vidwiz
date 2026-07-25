from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import uuid

from src.notes.models import Note
from src.notes.service import _build_ai_note_queue_payload


class _FakeLogger:
    def info(self, *_args, **_kwargs):
        return None

    def error(self, *_args, **_kwargs):
        return None

    def warning(self, *_args, **_kwargs):
        return None

    def inject_lambda_context(self, **_kwargs):
        return lambda function: function


def _install_powertools_stubs(monkeypatch):
    powertools = ModuleType("aws_lambda_powertools")
    powertools.Logger = _FakeLogger
    utilities = ModuleType("aws_lambda_powertools.utilities")
    parser = ModuleType("aws_lambda_powertools.utilities.parser")
    parser.envelopes = SimpleNamespace(SqsEnvelope=object())
    parser.event_parser = lambda **_kwargs: lambda function: function
    typing = ModuleType("aws_lambda_powertools.utilities.typing")
    typing.LambdaContext = object
    monkeypatch.setitem(sys.modules, "aws_lambda_powertools", powertools)
    monkeypatch.setitem(sys.modules, "aws_lambda_powertools.utilities", utilities)
    monkeypatch.setitem(
        sys.modules,
        "aws_lambda_powertools.utilities.parser",
        parser,
    )
    monkeypatch.setitem(
        sys.modules,
        "aws_lambda_powertools.utilities.typing",
        typing,
    )


def _load_handler(relative_path: str, monkeypatch):
    _install_powertools_stubs(monkeypatch)
    handler_path = (
        Path(__file__).resolve().parents[2]
        / "workers"
        / "lambdas"
        / relative_path
        / "handler.py"
    )
    module_name = f"test_{relative_path}_{uuid.uuid4().hex}"
    spec = spec_from_file_location(module_name, handler_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _set_worker_environment(monkeypatch):
    monkeypatch.setenv(
        "VIDWIZ_INTERNAL_API_BASE_URL",
        "https://internal.example",
    )
    monkeypatch.setenv("VIDWIZ_INTERNAL_API_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("SQS_AI_NOTE_QUEUE_URL", "note-queue")
    monkeypatch.setenv("SQS_AI_SUMMARY_QUEUE_URL", "summary-queue")
    monkeypatch.setenv("S3_TRANSCRIPT_BUCKET_NAME", "transcript-bucket")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-key")


def test_dispatcher_uses_domain_specific_queue_urls(monkeypatch):
    _set_worker_environment(monkeypatch)
    handler = _load_handler("transcript_dispatcher", monkeypatch)
    calls = []

    class FakeSqs:
        def send_message_batch(self, **kwargs):
            calls.append(kwargs)
            return {"Successful": [{"Id": "0"}]}

        def send_message(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(handler.boto3, "client", lambda _name: FakeSqs())

    handler.push_notes_to_sqs_batch([{"id": 1}])
    handler.push_summary_to_sqs("video-id")

    assert calls[0]["QueueUrl"] == "note-queue"
    assert calls[1]["QueueUrl"] == "summary-queue"


def test_ai_note_producer_payload_validates_against_worker_model(monkeypatch):
    _set_worker_environment(monkeypatch)
    worker = _load_handler("ai_note_worker", monkeypatch)
    note = Note(id=42, video_id="abc123", timestamp="01:23", user_id=7)

    payload = _build_ai_note_queue_payload(note)
    validated = worker.Note.model_validate_json(json.dumps(payload))

    assert validated.id == 42
    assert validated.video_id == "abc123"
    assert validated.timestamp == "01:23"
    assert validated.user_id == 7
