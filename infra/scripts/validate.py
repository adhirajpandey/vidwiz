#!/usr/bin/env python3
"""Run the complete infrastructure validation suite."""

import os
import subprocess
import sys
from pathlib import Path

INFRA_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_DIR = INFRA_DIR.parent
FIXTURE_ENV_FILE = "tests/fixtures/production.env"
NPM_COMMAND = "npm.cmd" if os.name == "nt" else "npm"


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def main() -> None:
    validation_commands = (
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
    )
    for command in validation_commands:
        run(command, cwd=INFRA_DIR)

    synthesis_env = os.environ | {"LAMBDA_ENV_FILE_PATH": FIXTURE_ENV_FILE}
    run(
        [NPM_COMMAND, "exec", "--", "cdk", "synth", "vidwiz-stack", "--quiet"],
        cwd=INFRA_DIR,
        env=synthesis_env,
    )
    run(["git", "diff", "--check"], cwd=REPOSITORY_DIR)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.exit(error.returncode)
