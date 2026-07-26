from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vidwiz_worker.clients import InternalApiClient, OpenRouterClient
from vidwiz_worker.config import WorkerSettings


class FakeLogger:
    def __init__(self):
        self.records = []

    def error(self, message, **kwargs):
        self.records.append(("error", message, kwargs.get("extra", {})))


@pytest.fixture
def settings(monkeypatch):
    environment = {
        "S3_TRANSCRIPT_BUCKET_NAME": "transcript-bucket",
        "VIDWIZ_INTERNAL_API_BASE_URL": "https://internal.example",
        "VIDWIZ_INTERNAL_API_ADMIN_TOKEN": "admin-token",
        "OPENROUTER_API_KEY": "openrouter-token",
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    return WorkerSettings.from_env()


def test_openrouter_client_uses_configured_model_and_auth(settings):
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "result"}}]}

    class Session:
        def post(self, *args, **kwargs):
            calls.append((args, kwargs))
            return Response()

    client = OpenRouterClient(settings, FakeLogger(), session=Session())

    assert client.complete("prompt") == "result"
    assert calls[0][0] == ("https://openrouter.ai/api/v1/chat/completions",)
    assert calls[0][1]["headers"]["Authorization"] == "Bearer openrouter-token"
    assert calls[0][1]["json"]["model"] == "google/gemini-3-flash-preview"


def test_openrouter_client_sends_structured_output_options(settings):
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": '{"summary": "result"}'}}]}

    class Session:
        def post(self, *args, **kwargs):
            calls.append((args, kwargs))
            return Response()

    client = OpenRouterClient(settings, FakeLogger(), session=Session())
    response_format = {
        "type": "json_schema",
        "json_schema": {"name": "video_summary"},
    }

    assert (
        client.complete(
            "prompt",
            response_format=response_format,
            require_parameters=True,
        )
        == '{"summary": "result"}'
    )
    assert calls[0][1]["json"]["response_format"] == response_format
    assert calls[0][1]["json"]["provider"] == {"require_parameters": True}


def test_internal_api_client_updates_ai_note(settings):
    calls = []

    class Response:
        status_code = 200

    class Session:
        def patch(self, *args, **kwargs):
            calls.append((args, kwargs))
            return Response()

    client = InternalApiClient(settings, FakeLogger(), session=Session())

    assert client.update_note(12, "Generated note") is True
    assert calls[0][0] == ("https://internal.example/v2/internal/notes/12",)
    assert calls[0][1]["json"] == {"text": "Generated note", "generated_by_ai": True}


def test_internal_api_client_updates_summary_and_questions(settings):
    calls = []

    class Response:
        status_code = 200

    class Session:
        def post(self, *args, **kwargs):
            calls.append((args, kwargs))
            return Response()

    client = InternalApiClient(settings, FakeLogger(), session=Session())
    questions = [
        "What is the first important idea?",
        "How does the speaker support that idea?",
        "What conclusion follows from the discussion?",
    ]

    assert client.update_summary("video-id", "Generated summary", questions)
    assert calls[0][0] == (
        "https://internal.example/v2/internal/videos/video-id/summary",
    )
    assert calls[0][1]["json"] == {
        "summary": "Generated summary",
        "miscellaneous_data": {"suggested_questions": questions},
    }


def test_openrouter_client_logs_safe_provider_error(settings):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "error": {
                    "code": "provider_unavailable",
                    "message": "sensitive provider response",
                    "metadata": {"raw": "do not log"},
                }
            }

    class Session:
        def post(self, *_args, **_kwargs):
            return Response()

    logger = FakeLogger()
    client = OpenRouterClient(settings, logger, session=Session())

    assert client.complete("private prompt") is None
    assert logger.records == [
        (
            "error",
            "OpenRouter API returned an error",
            {"error_code": "provider_unavailable"},
        )
    ]
    assert "sensitive provider response" not in str(logger.records)
