from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vidwiz_worker.config import WorkerSettings


def test_settings_require_shared_worker_credentials(monkeypatch):
    monkeypatch.delenv("S3_TRANSCRIPT_BUCKET_NAME", raising=False)

    with pytest.raises(AssertionError, match="S3_TRANSCRIPT_BUCKET_NAME"):
        WorkerSettings.from_env()
