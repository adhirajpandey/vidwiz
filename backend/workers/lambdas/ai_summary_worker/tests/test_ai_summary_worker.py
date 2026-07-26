from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import uuid

import pytest

WORKER_DIR = Path(__file__).resolve().parents[1]
SHARED_DIR = Path(__file__).resolve().parents[3] / "shared"
sys.path.insert(0, str(SHARED_DIR))


class FakeLogger:
    def info(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass

    def warning(self, *_args, **_kwargs):
        pass

    def inject_lambda_context(self, **_kwargs):
        return lambda function: function


def _install_powertools_stubs(monkeypatch):
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
    monkeypatch.setenv("MIN_SUMMARY_LENGTH", "1")
    monkeypatch.setenv("MAX_SUMMARY_LENGTH", "800")


def _load_module(filename, monkeypatch):
    _install_powertools_stubs(monkeypatch)
    _set_environment(monkeypatch)
    monkeypatch.syspath_prepend(str(WORKER_DIR))
    module_name = f"test_ai_summary_{filename.removesuffix('.py')}_{uuid.uuid4().hex}"
    spec = spec_from_file_location(module_name, WORKER_DIR / filename)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_process_summary_skips_existing_summary(monkeypatch):
    summary_service = _load_module("summary_service.py", monkeypatch)

    class Api:
        def get_video(self, _video_id):
            return {"title": "Video", "summary": "Existing summary"}

    class Unused:
        def __getattr__(self, _name):
            raise AssertionError("summary dependencies should not be called")

    monkeypatch.setattr(summary_service, "api", Api())
    monkeypatch.setattr(summary_service, "transcripts", Unused())
    monkeypatch.setattr(summary_service, "llm", Unused())

    summary_service.process_summary("video-id")


def test_process_batch_propagates_item_failure(monkeypatch):
    summary_service = _load_module("summary_service.py", monkeypatch)
    monkeypatch.setattr(
        summary_service,
        "process_summary",
        lambda _video_id: (_ for _ in ()).throw(RuntimeError("retry")),
    )

    with pytest.raises(RuntimeError, match="retry"):
        summary_service.process_batch([SimpleNamespace(video_id="video-id")])


def test_valid_summary_preserves_braces_in_transcript(monkeypatch):
    summary_service = _load_module("summary_service.py", monkeypatch)
    prompts = []
    monkeypatch.setattr(
        summary_service,
        "settings",
        SimpleNamespace(max_retries=1, min_summary_length=1, max_summary_length=100),
    )
    monkeypatch.setattr(
        summary_service,
        "llm",
        SimpleNamespace(
            complete=lambda prompt: prompts.append(prompt) or "Valid summary"
        ),
    )

    assert (
        summary_service._valid_summary(None, "Transcript with {literal} braces")
        == "Valid summary"
    )
    assert "Transcript with {literal} braces" in prompts[0]
    assert "{{literal}}" not in prompts[0]


def test_valid_summary_returns_none_after_invalid_final_retry(monkeypatch):
    summary_service = _load_module("summary_service.py", monkeypatch)
    monkeypatch.setattr(
        summary_service,
        "settings",
        SimpleNamespace(max_retries=2, min_summary_length=5, max_summary_length=10),
    )
    monkeypatch.setattr(
        summary_service,
        "llm",
        SimpleNamespace(complete=lambda _prompt: "too long for configured bounds"),
    )

    assert summary_service._valid_summary(None, "Transcript") is None


def test_handler_delegates_parsed_batch(monkeypatch):
    handler = _load_module("handler.py", monkeypatch)
    calls = []
    monkeypatch.setattr(
        handler.summary_service,
        "process_batch",
        lambda event: calls.append(event),
    )

    handler.lambda_handler(["summary"], object())

    assert calls == [["summary"]]
