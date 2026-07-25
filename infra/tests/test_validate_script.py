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

    validate.main()

    assert [command for command, _, _ in calls] == [
        [
            "uv",
            "run",
            "ruff",
            "format",
            "--check",
            "app.py",
            "vidwiz_infra",
            "scripts",
            "tests",
        ],
        ["uv", "run", "ruff", "check", "app.py", "vidwiz_infra", "scripts", "tests"],
        ["uv", "run", "mypy", "app.py", "vidwiz_infra", "scripts", "tests"],
        ["uv", "run", "pytest"],
        [validate.NPM_COMMAND, "exec", "--", "cdk", "synth", "vidwiz-stack", "--quiet"],
        ["git", "diff", "--check"],
    ]
    assert calls[4][2] is not None
    assert calls[4][2]["LAMBDA_ENV_FILE_PATH"] == "tests/fixtures/production.env"
    assert calls[5][1] == validate.REPOSITORY_DIR
