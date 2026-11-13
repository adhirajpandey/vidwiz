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

    client = OpenRouterClient(
        settings, FakeLogger(), model="summary-model", session=Session()
    )

    assert client.complete("prompt") == "result"
    assert calls[0][0] == ("https://openrouter.ai/api/v1/chat/completions",)
    assert calls[0][1]["headers"]["Authorization"] == "Bearer openrouter-token"
    assert calls[0][1]["json"]["model"] == "summary-model"


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

    client = OpenRouterClient(
        settings, FakeLogger(), model="summary-model", session=Session()
    )
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


def test_internal_api_client_saves_moment_ai(settings):
    calls = []

    class Response:
        status_code = 200

    class Session:
        def put(self, *args, **kwargs):
            calls.append((args, kwargs))
            return Response()

    client = InternalApiClient(settings, FakeLogger(), session=Session())

    assert client.save_moment_ai(12, "Generated note", "model/a") is True
    assert client.save_moment_ai(12, None) is True
    assert calls[0][0] == ("https://internal.example/v2/internal/moments/12/ai",)
    assert calls[0][1]["json"] == {"ai_text": "Generated note", "ai_model": "model/a"}
    assert calls[1][1]["json"] == {"ai_text": None, "ai_model": None}


def test_internal_api_client_propagates_only_bounded_correlation_ids(settings):
    calls = []

    class Response:
        status_code = 200

    class Session:
        def put(self, *args, **kwargs):
            calls.append((args, kwargs))
            return Response()

    client = InternalApiClient(settings, FakeLogger(), session=Session())

    assert client.save_moment_ai(12, "Generated note", correlation_id="trace:abc-123")
    assert calls[0][1]["headers"]["X-Correlation-ID"] == "trace:abc-123"

    assert client.save_moment_ai(12, None, correlation_id="bad value")
    assert "X-Correlation-ID" not in calls[1][1]["headers"]


def test_internal_api_client_updates_overview(settings):
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

    points = [{"text": "Point", "start_seconds": 1.0, "end_seconds": 2.0}]

    assert client.update_summary(
        "video-id", "Generated summary", questions, points, "model/b"
    )
    assert calls[0][0] == (
        "https://internal.example/v2/internal/videos/video-id/summary",
    )
    assert calls[0][1]["json"] == {
        "summary": "Generated summary",
        "miscellaneous_data": {
            "suggested_questions": questions,
            "key_points": points,
            "overview_model": "model/b",
        },
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
    client = OpenRouterClient(settings, logger, model="note-model", session=Session())

    assert client.complete("private prompt") is None
    assert logger.records == [
        (
            "error",
            "OpenRouter API returned an error",
            {"error_code": "provider_unavailable"},
        )
    ]
    assert "sensitive provider response" not in str(logger.records)


def test_fail_overview_posts_to_the_internal_route():
    from types import SimpleNamespace

    from vidwiz_worker.clients import InternalApiClient

    calls = []

    class Session:
        def post(self, url, **kwargs):
            calls.append((url, kwargs["json"]))
            return SimpleNamespace(status_code=200)

    settings = SimpleNamespace(
        internal_api_admin_token="token",
        internal_api_base_url="https://api.example",
        request_timeout=5,
    )
    client = InternalApiClient(
        settings, SimpleNamespace(error=print), session=Session()
    )

    assert client.fail_overview("abc123DEF45") is True
    assert calls == [
        ("https://api.example/v2/internal/videos/abc123DEF45/overview/failed", {})
    ]


@pytest.mark.parametrize(
    ("status_code", "kind"),
    [
        (403, "provider_quota"),
        (402, "provider_quota"),
        (429, "provider_rate_limit"),
        (500, "provider_error"),
    ],
)
def test_openrouter_client_names_why_a_request_failed(settings, status_code, kind):
    import requests

    class Response:
        def raise_for_status(self):
            error = requests.HTTPError("rejected")
            error.response = self
            raise error

    Response.status_code = status_code

    class Session:
        def post(self, *_args, **_kwargs):
            return Response()

    client = OpenRouterClient(settings, FakeLogger(), model="m", session=Session())

    assert client.complete("prompt") is None
    assert client.last_failure_kind == kind


def test_openrouter_client_names_timeouts(settings):
    import requests

    class Session:
        def post(self, *_args, **_kwargs):
            raise requests.Timeout("slow")

    client = OpenRouterClient(settings, FakeLogger(), model="m", session=Session())

    assert client.complete("prompt") is None
    assert client.last_failure_kind == "timeout"


def test_report_attempt_failure_posts_bounded_fields(settings):
    from types import SimpleNamespace

    calls = []

    class Session:
        def post(self, url, **kwargs):
            calls.append(
                (url, kwargs["json"], kwargs["headers"].get("X-Correlation-ID"))
            )
            return SimpleNamespace(status_code=204)

    client = InternalApiClient(settings, FakeLogger(), session=Session())

    assert client.report_attempt_failure("ai_moment", "provider_quota", 2, False, "c-1")
    assert calls == [
        (
            "https://internal.example/v2/internal/workflows/ai_moment/attempt-failures",
            {"reason": "provider_quota", "attempt": 2, "final": False},
            "c-1",
        )
    ]
