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
        "LAMBDA_ENV_FILE": config or FIXTURE_ENV.read_text(),
        "EXPECTED_AWS_ACCOUNT_ID": "123456789012",
        "RUNNER_TEMP": str(tmp_path),
        "GITHUB_ENV": str(github_environment),
    }


def test_prepares_private_validated_configuration_and_exports_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    environment = _environment(tmp_path)

    config_path = prepare_production_config(environment)

    assert config_path.read_text() == FIXTURE_ENV.read_text()
    if os.name == "posix":
        assert os.stat(config_path).st_mode & 0o777 == 0o600
    assert Path(environment["GITHUB_ENV"]).read_text() == (
        f"LAMBDA_ENV_FILE_PATH={config_path}\n"
    )
    output = capsys.readouterr().out
    assert "::add-mask::fixture-admin-token" in output
    assert "::add-mask::fixture-openrouter-key" in output


def test_rejects_account_mismatch_without_leaving_configuration(tmp_path: Path) -> None:
    environment = _environment(tmp_path)
    environment["EXPECTED_AWS_ACCOUNT_ID"] = "210987654321"

    with pytest.raises(ValueError, match="must match"):
        prepare_production_config(environment)

    assert not list(tmp_path.glob("vidwiz-production-*.env"))


@pytest.mark.parametrize(
    "missing", ["LAMBDA_ENV_FILE", "EXPECTED_AWS_ACCOUNT_ID", "GITHUB_ENV"]
)
def test_rejects_missing_required_workflow_input(tmp_path: Path, missing: str) -> None:
    environment = _environment(tmp_path)
    del environment[missing]

    with pytest.raises(ValueError):
        prepare_production_config(environment)

    assert not list(tmp_path.glob("vidwiz-production-*.env"))


@pytest.mark.parametrize("config_file", [None, ""])
def test_cleanup_succeeds_without_a_config_file(config_file: str | None) -> None:
    environment = {}
    if config_file is not None:
        environment["CONFIG_FILE"] = config_file

    cleanup_production_config(environment)


def test_cleanup_removes_the_temporary_config_file(tmp_path: Path) -> None:
    config_path = tmp_path / "vidwiz-production.env"
    config_path.write_text("secret=value\n")

    cleanup_production_config({"CONFIG_FILE": str(config_path)})

    assert not config_path.exists()


def test_cleanup_succeeds_when_the_config_path_no_longer_exists(
    tmp_path: Path,
) -> None:
    cleanup_production_config(
        {"CONFIG_FILE": str(tmp_path / "missing-production.env")}
    )
