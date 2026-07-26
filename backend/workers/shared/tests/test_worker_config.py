from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vidwiz_worker.config import WorkerSettings


def _set_required_environment(monkeypatch):
    for name, value in {
        "S3_TRANSCRIPT_BUCKET_NAME": "bucket",
        "VIDWIZ_INTERNAL_API_BASE_URL": "https://internal.example",
        "VIDWIZ_INTERNAL_API_ADMIN_TOKEN": "admin-token",
        "OPENROUTER_API_KEY": "openrouter-token",
    }.items():
        monkeypatch.setenv(name, value)


def test_settings_require_shared_worker_credentials(monkeypatch):
    monkeypatch.delenv("S3_TRANSCRIPT_BUCKET_NAME", raising=False)

    with pytest.raises(AssertionError, match="S3_TRANSCRIPT_BUCKET_NAME"):
        WorkerSettings.from_env()


def test_settings_use_question_length_defaults(monkeypatch):
    _set_required_environment(monkeypatch)
    monkeypatch.delenv("MIN_QUESTION_LENGTH", raising=False)
    monkeypatch.delenv("MAX_QUESTION_LENGTH", raising=False)

    settings = WorkerSettings.from_env()

    assert settings.min_question_length == 20
    assert settings.max_question_length == 120


@pytest.mark.parametrize(
    ("minimum", "maximum"),
    [
        ("0", "120"),
        ("20", "501"),
        ("121", "120"),
    ],
)
def test_settings_reject_invalid_question_length_range(monkeypatch, minimum, maximum):
    _set_required_environment(monkeypatch)
    monkeypatch.setenv("MIN_QUESTION_LENGTH", minimum)
    monkeypatch.setenv("MAX_QUESTION_LENGTH", maximum)

    with pytest.raises(ValueError, match="question length"):
        WorkerSettings.from_env()
