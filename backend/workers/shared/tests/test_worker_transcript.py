from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vidwiz_worker.config import WorkerSettings
from vidwiz_worker.transcript import S3TranscriptRepository


class FakeLogger:
    def __init__(self):
        self.records = []

    def info(self, message, **kwargs):
        self.records.append(("info", message, kwargs.get("extra", {})))

    def warning(self, message, **kwargs):
        self.records.append(("warning", message, kwargs.get("extra", {})))

    def error(self, message, **kwargs):
        self.records.append(("error", message, kwargs.get("extra", {})))


@pytest.fixture
def settings(monkeypatch):
    environment = {
        "S3_TRANSCRIPT_BUCKET_NAME": "transcript-bucket",
        "VIDWIZ_INTERNAL_API_BASE_URL": "https://internal.example",
        "VIDWIZ_INTERNAL_API_ADMIN_TOKEN": "admin-token",
        "OPENROUTER_API_KEY": "openrouter-token",
        "TRANSCRIPT_FETCH_MAX_RETRIES": "3",
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
    logger = FakeLogger()
    repository = S3TranscriptRepository(settings, logger, s3_client=client)

    assert repository.get("video-id") == [{"offset": 1, "text": "hello"}]
    assert client.calls == 2
    assert [record[0] for record in logger.records] == ["warning", "info"]
    assert logger.records[0][2]["error_type"] == "RuntimeError"
    assert logger.records[1][2]["segment_count"] == 1


def test_transcript_repository_logs_one_terminal_error(settings):
    class S3Client:
        def get_object(self, **_kwargs):
            raise RuntimeError("private failure detail")

    logger = FakeLogger()
    repository = S3TranscriptRepository(settings, logger, s3_client=S3Client())

    assert repository.get("video-id") is None
    assert [record[0] for record in logger.records] == [
        "warning",
        "warning",
        "error",
    ]
    assert logger.records[-1][1] == "Failed to load transcript from S3"
    assert logger.records[-1][2]["attempt"] == 3
    assert logger.records[-1][2]["error_type"] == "RuntimeError"
    assert "private failure detail" not in str(logger.records)
