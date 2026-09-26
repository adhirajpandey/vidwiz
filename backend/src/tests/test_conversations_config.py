import pytest
from pydantic import ValidationError

from src.config import Settings
from src.tests.test_config_settings import _set_required_env


def test_transcript_bucket_uses_domain_specific_name(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("S3_TRANSCRIPT_BUCKET_NAME", "transcript-bucket")

    configured = Settings(_env_file=None)

    assert configured.s3_transcript_bucket_name == "transcript-bucket"


def test_wiz_model_uses_default(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.delenv("WIZ_MODEL", raising=False)

    configured = Settings(_env_file=None)

    assert configured.wiz_model == "minimax/minimax-m2.5"


def test_wiz_model_uses_override(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("WIZ_MODEL", "custom-wiz-model")

    configured = Settings(_env_file=None)

    assert configured.wiz_model == "custom-wiz-model"


def test_wiz_model_rejects_blank_value(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.setenv("WIZ_MODEL", "   ")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_wiz_token_budget_default_and_override(monkeypatch):
    _set_required_env(monkeypatch)
    monkeypatch.delenv("WIZ_MAX_TOKENS", raising=False)
    assert Settings(_env_file=None).wiz_max_tokens == 8192
    monkeypatch.setenv("WIZ_MAX_TOKENS", "2048")
    assert Settings(_env_file=None).wiz_max_tokens == 2048
