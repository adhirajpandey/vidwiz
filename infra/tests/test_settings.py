from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from vidwiz_infra.settings import ProductionDeploymentConfig

FIXTURE_ENV = Path(__file__).parent / "fixtures" / "production.env"


def test_loads_valid_fixture_and_protects_secrets() -> None:
    settings = ProductionDeploymentConfig.from_env_file(FIXTURE_ENV)

    assert settings.aws_region == "ap-south-1"
    assert settings.vidwiz_internal_api_base_url == "https://example.invalid"
    assert settings.min_question_length == 20
    assert settings.max_question_length == 120
    assert settings.summary_model == "fixture-summary-model"
    assert settings.ai_note_model == "fixture-note-model"
    assert isinstance(settings.vidwiz_internal_api_admin_token, SecretStr)
    assert "fixture-admin-token" not in repr(settings)
    assert "fixture-openrouter-key" not in repr(settings)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("AWS_ACCOUNT_ID", "not-an-account"),
        ("AWS_REGION", "us-east-1"),
        ("AI_NOTE_TIMEOUT_SECONDS", "0"),
        ("AI_SUMMARY_MEMORY_MB", "127"),
        ("VIDWIZ_INTERNAL_API_BASE_URL", "not-a-url"),
        ("VIDWIZ_INTERNAL_API_ADMIN_TOKEN", ""),
        ("MAX_NOTE_LENGTH", "20"),
        ("MAX_QUESTION_LENGTH", "501"),
    ],
)
def test_rejects_invalid_production_values(
    tmp_path: Path, key: str, value: str
) -> None:
    original_line = next(
        line for line in FIXTURE_ENV.read_text().splitlines() if line.startswith(key)
    )
    text = FIXTURE_ENV.read_text().replace(
        original_line,
        f"{key}={value}",
    )
    env_file = tmp_path / "invalid.env"
    env_file.write_text(text)

    with pytest.raises(ValidationError):
        ProductionDeploymentConfig.from_env_file(env_file)


def test_missing_configuration_does_not_disclose_secrets(tmp_path: Path) -> None:
    env_file = tmp_path / "missing.env"
    env_file.write_text("VIDWIZ_INTERNAL_API_ADMIN_TOKEN=do-not-disclose\n")

    with pytest.raises(ValidationError) as error:
        ProductionDeploymentConfig.from_env_file(env_file)

    assert "do-not-disclose" not in str(error.value)


def test_rejects_inverted_question_length_range(tmp_path: Path) -> None:
    text = FIXTURE_ENV.read_text().replace(
        "MIN_QUESTION_LENGTH=20",
        "MIN_QUESTION_LENGTH=121",
    )
    env_file = tmp_path / "invalid-question-range.env"
    env_file.write_text(text)

    with pytest.raises(ValidationError, match="MIN_QUESTION_LENGTH"):
        ProductionDeploymentConfig.from_env_file(env_file)


def test_explicit_configuration_file_ignores_ambient_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AWS_ACCOUNT_ID", "210987654321")
    monkeypatch.setenv("SUMMARY_MODEL", "ambient-summary-model")
    monkeypatch.setenv("AI_NOTE_MODEL", "ambient-note-model")
    monkeypatch.setenv("VIDWIZ_INTERNAL_API_BASE_URL", "https://ambient.invalid")
    monkeypatch.setenv("VIDWIZ_INTERNAL_API_ADMIN_TOKEN", "ambient-admin-token")

    settings = ProductionDeploymentConfig.from_env_file(FIXTURE_ENV)

    assert settings.aws_account_id == "123456789012"
    assert settings.summary_model == "fixture-summary-model"
    assert settings.ai_note_model == "fixture-note-model"
    assert settings.vidwiz_internal_api_base_url == "https://example.invalid"
    assert (
        settings.vidwiz_internal_api_admin_token.get_secret_value()
        == "fixture-admin-token"
    )


def test_missing_model_fields_use_defaults_instead_of_ambient_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    text = "\n".join(
        line
        for line in FIXTURE_ENV.read_text().splitlines()
        if not line.startswith(("SUMMARY_MODEL=", "AI_NOTE_MODEL="))
    )
    env_file = tmp_path / "models-omitted.env"
    env_file.write_text(f"{text}\n")
    monkeypatch.setenv("SUMMARY_MODEL", "ambient-summary-model")
    monkeypatch.setenv("AI_NOTE_MODEL", "ambient-note-model")

    settings = ProductionDeploymentConfig.from_env_file(env_file)

    assert settings.summary_model == "qwen/qwen3.5-35b-a3b"
    assert settings.ai_note_model == "z-ai/glm-5.3-flash"


@pytest.mark.parametrize("name", ["SUMMARY_MODEL", "AI_NOTE_MODEL"])
def test_rejects_blank_model_values(tmp_path: Path, name: str) -> None:
    original_line = next(
        line for line in FIXTURE_ENV.read_text().splitlines() if line.startswith(name)
    )
    env_file = tmp_path / "blank-model.env"
    env_file.write_text(FIXTURE_ENV.read_text().replace(original_line, f"{name}=   "))

    with pytest.raises(ValidationError):
        ProductionDeploymentConfig.from_env_file(env_file)
