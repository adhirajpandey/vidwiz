from importlib.util import module_from_spec, spec_from_file_location
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import uuid

import pytest

REQUIRED_BACKEND_ENVIRONMENT = {
    "ENVIRONMENT": "test",
    "SECRET_KEY": "test-secret",
    "VIDWIZ_INTERNAL_API_ADMIN_TOKEN": "test-admin-token",
    "GOOGLE_CLIENT_ID": "test-google-client-id",
    "SQS_AI_NOTE_QUEUE_URL": "test-queue-url",
    "AWS_ACCESS_KEY_ID": "test-aws-key",
    "AWS_SECRET_ACCESS_KEY": "test-aws-secret",
    "DODO_PAYMENTS_API_KEY": "test-dodo-key",
    "DODO_PAYMENTS_WEBHOOK_KEY": "test-dodo-webhook",
    "DODO_PAYMENTS_ENVIRONMENT": "test_mode",
    "DODO_PAYMENTS_RETURN_URL": "https://example.com/return",
    "DODO_CREDIT_PRODUCTS": (
        '[{"product_id":"pdt_test","credits":200,"price_inr":20,"name":"Credits"}]'
    ),
}
for environment_name, environment_value in REQUIRED_BACKEND_ENVIRONMENT.items():
    os.environ.setdefault(environment_name, environment_value)

from src.internal.schemas import PendingMoment  # noqa: E402
from src.moments.models import Moment as DatabaseMoment  # noqa: E402
from src.moments.service import queue_payload  # noqa: E402

WORKER_DIR = Path(__file__).resolve().parents[1]
SHARED_DIR = Path(__file__).resolve().parents[3] / "shared"
sys.path.insert(0, str(SHARED_DIR))

from vidwiz_worker.models import Moment  # noqa: E402


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

    def warning(self, message, **kwargs):
        self._record("warning", message, kwargs)

    def inject_lambda_context(self, **kwargs):
        FakeLogger.inject_options = kwargs
        return lambda function: function


def _install_powertools_stubs(monkeypatch):
    FakeLogger.inject_options = None
    powertools = ModuleType("aws_lambda_powertools")
    powertools.Logger = FakeLogger
    utilities = ModuleType("aws_lambda_powertools.utilities")
    parser = ModuleType("aws_lambda_powertools.utilities.parser")
    parser.envelopes = SimpleNamespace(SqsEnvelope=object())
    parser.event_parser = lambda **_kwargs: lambda function: function
    typing = ModuleType("aws_lambda_powertools.utilities.typing")
    typing.LambdaContext = object
    monkeypatch.setitem(sys.modules, "aws_lambda_powertools", powertools)
    monkeypatch.setitem(sys.modules, "aws_lambda_powertools.utilities", utilities)
    monkeypatch.setitem(sys.modules, "aws_lambda_powertools.utilities.parser", parser)
    monkeypatch.setitem(sys.modules, "aws_lambda_powertools.utilities.typing", typing)


def _set_environment(monkeypatch):
    monkeypatch.setenv("S3_TRANSCRIPT_BUCKET_NAME", "transcript-bucket")
    monkeypatch.setenv("VIDWIZ_INTERNAL_API_BASE_URL", "https://internal.example")
    monkeypatch.setenv("VIDWIZ_INTERNAL_API_ADMIN_TOKEN", "admin-token")
    monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-token")
    monkeypatch.setenv("MIN_NOTE_LENGTH", "1")
    monkeypatch.setenv("MAX_NOTE_LENGTH", "120")


def _load_module(filename, monkeypatch):
    _install_powertools_stubs(monkeypatch)
    _set_environment(monkeypatch)
    monkeypatch.syspath_prepend(str(WORKER_DIR))
    module_name = f"test_ai_note_{filename.removesuffix('.py')}_{uuid.uuid4().hex}"
    spec = spec_from_file_location(module_name, WORKER_DIR / filename)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_producer_payloads_validate_against_worker_model():
    moment = DatabaseMoment(id=42, video_id="abc123", at_seconds=83, user_id=7)

    for payload in (
        queue_payload(moment),
        PendingMoment.model_validate(moment).model_dump(mode="json"),
    ):
        validated = Moment.model_validate_json(json.dumps(payload))
        assert validated == Moment(id=42, video_id="abc123", at_seconds=83, user_id=7)


def test_process_moment_uses_video_title_and_persists(monkeypatch):
    note_service = _load_module("note_service.py", monkeypatch)

    class Transcripts:
        def get(self, _video_id):
            return [{"offset": 60, "text": "Transcript context"}]

    class Api:
        def __init__(self):
            self.updated = None

        def get_video(self, _video_id):
            return {"title": "Fallback title"}

        def save_moment_ai(self, moment_id, ai_text, ai_model=None):
            self.updated = (moment_id, ai_text, ai_model)
            return True

    class Llm:
        def complete(self, _prompt):
            return "Generated note"

    api = Api()
    monkeypatch.setattr(note_service, "transcripts", Transcripts())
    monkeypatch.setattr(note_service, "api", api)
    monkeypatch.setattr(note_service, "llm", Llm())

    note_service.process_moment(
        Moment(id=12, video_id="video-id", at_seconds=60, user_id=2)
    )

    assert api.updated == (12, "Generated note", note_service.settings.ai_note_model)
    assert note_service.logger.records[-1] == (
        "info",
        "AI moment saved",
        {"moment_id": 12, "video_id": "video-id"},
    )


@pytest.mark.parametrize(
    ("transcript", "context"),
    [(None, None), ([{"offset": 60, "text": "Transcript context"}], None)],
)
def test_process_moment_marks_missing_context_failed(monkeypatch, transcript, context):
    note_service = _load_module("note_service.py", monkeypatch)
    saved = []

    class Transcripts:
        def get(self, _video_id):
            return transcript

    class Api:
        def save_moment_ai(self, moment_id, ai_text):
            saved.append((moment_id, ai_text))
            return True

    monkeypatch.setattr(note_service, "transcripts", Transcripts())
    monkeypatch.setattr(note_service, "api", Api())
    monkeypatch.setattr(note_service, "relevant_context", lambda *_args: context)

    note_service.process_moment(
        Moment(id=12, video_id="video-id", at_seconds=60, user_id=2)
    )

    assert saved == [(12, None)]


def test_process_moment_retries_generation_failures(monkeypatch):
    note_service = _load_module("note_service.py", monkeypatch)

    class Transcripts:
        def get(self, _video_id):
            return [{"offset": 60, "text": "Transcript context"}]

    class Api:
        def get_video(self, _video_id):
            return None

    monkeypatch.setattr(note_service, "transcripts", Transcripts())
    monkeypatch.setattr(note_service, "api", Api())
    monkeypatch.setattr(note_service, "_valid_note", lambda *_args: None)

    with pytest.raises(RuntimeError):
        note_service.process_moment(
            Moment(id=12, video_id="video-id", at_seconds=60, user_id=2)
        )


def test_process_moment_raises_when_save_fails(monkeypatch):
    note_service = _load_module("note_service.py", monkeypatch)

    class Transcripts:
        def get(self, _video_id):
            return [{"offset": 60, "text": "Transcript context"}]

    class Api:
        def get_video(self, _video_id):
            return {"title": "Fallback title"}

        def save_moment_ai(self, _moment_id, _ai_text, _ai_model=None):
            return False

    monkeypatch.setattr(note_service, "transcripts", Transcripts())
    monkeypatch.setattr(note_service, "api", Api())
    monkeypatch.setattr(note_service, "_valid_note", lambda *_args: "Generated note")

    with pytest.raises(RuntimeError):
        note_service.process_moment(
            Moment(id=12, video_id="video-id", at_seconds=60, user_id=2)
        )


def test_valid_note_returns_none_after_invalid_final_retry(monkeypatch):
    note_service = _load_module("note_service.py", monkeypatch)
    monkeypatch.setattr(
        note_service,
        "settings",
        SimpleNamespace(max_retries=2, min_note_length=5, max_note_length=10),
    )
    monkeypatch.setattr(
        note_service,
        "llm",
        SimpleNamespace(complete=lambda _prompt: "too long for configured bounds"),
    )

    assert note_service._valid_note(None, 1, "Transcript") is None
    warnings = [
        record for record in note_service.logger.records if record[0] == "warning"
    ]
    assert len(warnings) == 2
    assert warnings[-1][1] == "Generated AI note has invalid length"
    assert warnings[-1][2] == {
        "attempt": 2,
        "max_retries": 2,
        "generated_length": 30,
    }
    assert "too long for configured bounds" not in str(warnings)


def test_process_batch_propagates_item_failure(monkeypatch):
    note_service = _load_module("note_service.py", monkeypatch)
    monkeypatch.setattr(
        note_service,
        "process_moment",
        lambda _note: (_ for _ in ()).throw(RuntimeError("retry")),
    )

    with pytest.raises(RuntimeError, match="retry"):
        note_service.process_batch(
            [Moment(id=12, video_id="video-id", at_seconds=60, user_id=2)]
        )


def test_handler_delegates_parsed_batch(monkeypatch):
    handler = _load_module("handler.py", monkeypatch)
    calls = []
    monkeypatch.setattr(
        handler.note_service,
        "process_batch",
        lambda event: calls.append(event),
    )

    handler.lambda_handler(["note"], object())

    assert calls == [["note"]]
    assert FakeLogger.inject_options == {"log_event": False}
