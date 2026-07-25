import os
from pathlib import Path

import pytest

from scripts.prepare_production_config import (
    cleanup_production_config,
    prepare_production_config,
)

FIXTURE_ENV = Path(__file__).parent / "fixtures" / "production.env"


def _environment(tmp_path: Path, config: str | None = None) -> dict[str, str]:
    github_environment = tmp_path / "github.env"
    return {
        "PRODUCTION_DEPLOYMENT_ENV": config or FIXTURE_ENV.read_text(),
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_ENV": str(github_environment),
    }


def test_prepares_private_validated_configuration_and_exports_target(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    environment = _environment(tmp_path)

    config_path = prepare_production_config(environment)

    assert config_path.read_text() == FIXTURE_ENV.read_text()
    if os.name == "posix":
        assert os.stat(config_path).st_mode & 0o777 == 0o600
    assert Path(environment["GITHUB_ENV"]).read_text() == (
        f"VIDWIZ_PRODUCTION_CONFIG_PATH={config_path}\n"
        "VIDWIZ_PRODUCTION_AWS_ACCOUNT_ID=123456789012\n"
        "VIDWIZ_PRODUCTION_AWS_REGION=ap-south-1\n"
    )
    output = capsys.readouterr().out
    assert "::add-mask::fixture-admin-token" in output
    assert "::add-mask::fixture-openrouter-key" in output


def test_rejects_invalid_configuration_without_leaving_file(tmp_path: Path) -> None:
    invalid_config = FIXTURE_ENV.read_text().replace(
        "AWS_ACCOUNT_ID=123456789012", "AWS_ACCOUNT_ID=not-an-account"
    )

    with pytest.raises(ValueError):
        prepare_production_config(_environment(tmp_path, invalid_config))

    assert not list(tmp_path.glob("vidwiz-production-config-*.env"))


@pytest.mark.parametrize("missing", ["PRODUCTION_DEPLOYMENT_ENV", "GITHUB_ENV"])
def test_rejects_missing_required_workflow_input(tmp_path: Path, missing: str) -> None:
    environment = _environment(tmp_path)
    del environment[missing]

    with pytest.raises(ValueError):
        prepare_production_config(environment)

    assert not list(tmp_path.glob("vidwiz-production-config-*.env"))


@pytest.mark.parametrize("config_file", [None, ""])
def test_cleanup_succeeds_without_a_config_file(config_file: str | None) -> None:
    environment = {}
    if config_file is not None:
        environment["CONFIG_FILE"] = config_file

    cleanup_production_config(environment)


def test_cleanup_removes_the_temporary_config_file(tmp_path: Path) -> None:
    config_path = tmp_path / "vidwiz-production-config.env"
    config_path.write_text("secret=value\n")

    cleanup_production_config({"CONFIG_FILE": str(config_path)})

    assert not config_path.exists()


def test_cleanup_succeeds_when_the_config_path_no_longer_exists(
    tmp_path: Path,
) -> None:
    cleanup_production_config(
        {"CONFIG_FILE": str(tmp_path / "missing-production-config.env")}
    )
