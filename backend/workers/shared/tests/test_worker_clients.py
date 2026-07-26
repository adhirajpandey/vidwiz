from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vidwiz_worker.clients import InternalApiClient, OpenRouterClient
from vidwiz_worker.config import WorkerSettings


class FakeLogger:
    def error(self, *_args, **_kwargs):
        pass


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
