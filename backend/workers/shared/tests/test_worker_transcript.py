from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vidwiz_worker.config import WorkerSettings
from vidwiz_worker.transcript import S3TranscriptRepository


class FakeLogger:
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
    }
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    return WorkerSettings.from_env()


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
