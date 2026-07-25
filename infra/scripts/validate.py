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
LAMBDA_DIRECTORIES = (
    REPOSITORY_DIR / "backend/workers/lambdas/transcript_dispatcher",
    REPOSITORY_DIR / "backend/workers/lambdas/ai_note_worker",
    REPOSITORY_DIR / "backend/workers/lambdas/ai_summary_worker",
)


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def main() -> None:
    validation_commands = (
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
    )
    for command in validation_commands:
        run(command, cwd=INFRA_DIR)

    for lambda_directory in LAMBDA_DIRECTORIES:
        run(["uv", "lock", "--check"], cwd=lambda_directory)

    synthesis_env = os.environ | {"VIDWIZ_PRODUCTION_CONFIG_PATH": FIXTURE_ENV_FILE}
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
