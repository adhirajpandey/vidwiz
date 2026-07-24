from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from vidwiz_infra.settings import ProductionSettings

FIXTURE_ENV = Path(__file__).parent / "fixtures" / "production.env"


def test_loads_valid_fixture_and_protects_secrets() -> None:
    settings = ProductionSettings.from_env_file(FIXTURE_ENV)

    assert settings.aws_region == "ap-south-1"
    assert settings.vidwiz_endpoint == "https://example.invalid"
    assert isinstance(settings.vidwiz_token, SecretStr)
    assert "fixture-admin-token" not in repr(settings)
    assert "fixture-openrouter-key" not in repr(settings)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("AWS_ACCOUNT_ID", "not-an-account"),
        ("AWS_REGION", "us-east-1"),
        ("AI_NOTE_TIMEOUT_SECONDS", "0"),
        ("AI_SUMMARY_MEMORY_MB", "127"),
        ("VIDWIZ_ENDPOINT", "not-a-url"),
        ("VIDWIZ_TOKEN", ""),
        ("MAX_NOTE_LENGTH", "20"),
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
        ProductionSettings.from_env_file(env_file)


def test_missing_configuration_does_not_disclose_secrets(tmp_path: Path) -> None:
    env_file = tmp_path / "missing.env"
    env_file.write_text("VIDWIZ_TOKEN=do-not-disclose\n")

    with pytest.raises(ValidationError) as error:
        ProductionSettings.from_env_file(env_file)

    assert "do-not-disclose" not in str(error.value)
