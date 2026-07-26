from pathlib import Path

import pytest

from scripts import validate


def test_runs_all_validation_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], Path, dict[str, str] | None]] = []

    def record(
        command: list[str], *, cwd: Path, env: dict[str, str] | None = None
    ) -> None:
        calls.append((command, cwd, env))

    monkeypatch.setattr(validate, "run", record)
    artifact_validation_calls = []
    monkeypatch.setattr(
        validate,
        "validate_lambda_artifacts",
        lambda: artifact_validation_calls.append(True),
    )

    validate.main()

    assert [command for command, _, _ in calls] == [
        [
            "uv",
            "run",
            "--locked",
            "ruff",
            "format",
            "--check",
            "app.py",
            "vidwiz_infra",
            "scripts",
            "tests",
        ],
        [
            "uv",
            "run",
            "--locked",
            "ruff",
            "check",
            "app.py",
            "vidwiz_infra",
            "scripts",
            "tests",
        ],
        ["uv", "run", "--locked", "mypy", "app.py", "vidwiz_infra", "scripts", "tests"],
        ["uv", "run", "--locked", "pytest"],
        ["uv", "lock", "--check"],
        ["uv", "lock", "--check"],
        ["uv", "lock", "--check"],
        [validate.NPM_COMMAND, "exec", "--", "cdk", "synth", "vidwiz-stack", "--quiet"],
        ["git", "diff", "--check"],
    ]
    assert [cwd for _, cwd, _ in calls[4:7]] == list(validate.LAMBDA_DIRECTORIES)
    assert calls[7][2] is not None
    assert (
        calls[7][2]["VIDWIZ_PRODUCTION_CONFIG_PATH"] == "tests/fixtures/production.env"
    )
    assert calls[8][1] == validate.REPOSITORY_DIR
    assert artifact_validation_calls == [True]


def _write_lambda_artifacts(cdk_output: Path) -> None:
    for index, service_file in enumerate(sorted(validate.LAMBDA_SERVICE_FILES)):
        asset = cdk_output / f"asset.{index}"
        asset.mkdir()
        (asset / "handler.py").touch()
        (asset / service_file).touch()
        if service_file != "dispatch_service.py":
            package = asset / validate.AI_WORKER_PACKAGE
            package.mkdir()
            (package / "__init__.py").touch()


def test_validates_lambda_artifact_layout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cdk_output = tmp_path / "cdk.out"
    cdk_output.mkdir()
    _write_lambda_artifacts(cdk_output)
    monkeypatch.setattr(validate, "INFRA_DIR", tmp_path)

    validate.validate_lambda_artifacts()


def test_rejects_tests_in_lambda_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cdk_output = tmp_path / "cdk.out"
    cdk_output.mkdir()
    _write_lambda_artifacts(cdk_output)
    (cdk_output / "asset.0" / "tests").mkdir()
    monkeypatch.setattr(validate, "INFRA_DIR", tmp_path)

    with pytest.raises(RuntimeError, match="must not contain"):
        validate.validate_lambda_artifacts()


def test_rejects_bytecode_in_lambda_artifacts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cdk_output = tmp_path / "cdk.out"
    cdk_output.mkdir()
    _write_lambda_artifacts(cdk_output)
    bytecode_cache = cdk_output / "asset.0" / "__pycache__"
    bytecode_cache.mkdir()
    (bytecode_cache / "handler.cpython-313.pyc").touch()
    monkeypatch.setattr(validate, "INFRA_DIR", tmp_path)

    with pytest.raises(RuntimeError, match="bytecode"):
        validate.validate_lambda_artifacts()
