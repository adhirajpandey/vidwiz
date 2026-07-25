from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "workers" / "shared"))

from vidwiz_worker.clients import InternalApiClient, OpenRouterClient
from vidwiz_worker.config import WorkerSettings
from vidwiz_worker.models import Note, SummaryRequest
from vidwiz_worker.services import AiNoteService, AiSummaryService
from vidwiz_worker.transcript import S3TranscriptRepository


class FakeLogger:
    def debug(self, *_args, **_kwargs):
        pass

    def info(self, *_args, **_kwargs):
        pass

    def warning(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


@pytest.fixture
def settings(monkeypatch):
    environment = {
        "S3_TRANSCRIPT_BUCKET_NAME": "transcript-bucket",
        "VIDWIZ_INTERNAL_API_BASE_URL": "https://internal.example",
        "VIDWIZ_INTERNAL_API_ADMIN_TOKEN": "admin-token",
        "OPENROUTER_API_KEY": "openrouter-token",
        "TRANSCRIPT_FETCH_RETRY_DELAY": "0",
        "MIN_NOTE_LENGTH": "1",
        "MAX_NOTE_LENGTH": "120",
        "MIN_SUMMARY_LENGTH": "1",
        "MAX_SUMMARY_LENGTH": "800",
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    return WorkerSettings.from_env()


def test_settings_require_shared_worker_credentials(monkeypatch):
    monkeypatch.delenv("S3_TRANSCRIPT_BUCKET_NAME", raising=False)

    with pytest.raises(AssertionError, match="S3_TRANSCRIPT_BUCKET_NAME"):
        WorkerSettings.from_env()


def test_transcript_repository_retries_and_returns_json(settings):
    class Body:
        def read(self):
            return b'[{"offset": 1, "text": "hello"}]'

    class S3Client:
        calls = 0

        def get_object(self, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("not ready")
            return {"Body": Body()}

    client = S3Client()
    repository = S3TranscriptRepository(settings, FakeLogger(), s3_client=client)

    assert repository.get("video-id") == [{"offset": 1, "text": "hello"}]
    assert client.calls == 2


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


def test_note_service_falls_back_to_video_metadata_and_persists(settings):
    class Transcripts:
        def get(self, _video_id):
            return [{"offset": 60, "text": "Transcript context"}]

    class Api:
        def __init__(self):
            self.updated = None

        def get_video(self, _video_id):
            return {"title": "Fallback title"}

        def update_note(self, note_id, text):
            self.updated = (note_id, text)
            return True

    class Llm:
        def complete(self, _prompt):
            return "Generated note"

    api = Api()
    service = AiNoteService(
        settings, FakeLogger(), transcripts=Transcripts(), api=api, llm=Llm()
    )

    service.process(Note(id=12, video_id="video-id", timestamp="01:00", user_id=2))

    assert api.updated == (12, "Generated note")


def test_summary_service_skips_existing_summary(settings):
    class Api:
        def get_video(self, _video_id):
            return {"title": "Video", "summary": "Existing summary"}

    class Unused:
        def __getattr__(self, _name):
            raise AssertionError("summary dependencies should not be called")

    service = AiSummaryService(
        settings,
        FakeLogger(),
        transcripts=Unused(),
        api=Api(),
        llm=Unused(),
    )

    service.process(SummaryRequest(video_id="video-id").video_id)
