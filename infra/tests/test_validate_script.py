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
        "validate_ai_worker_artifacts",
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
