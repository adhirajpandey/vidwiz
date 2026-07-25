#!/usr/bin/env python3
"""Materialize validated GitHub production configuration for CDK."""

import os
import tempfile
from pathlib import Path

from vidwiz_infra.settings import ProductionSettings


def append_github_environment(path: Path, name: str, value: str) -> None:
    with path.open("a", encoding="utf-8") as environment_file:
        environment_file.write(f"{name}={value}\n")


def prepare_production_config(environ: dict[str, str]) -> Path:
    raw_config = environ.get("LAMBDA_ENV_FILE")
    if not raw_config:
        raise ValueError("LAMBDA_ENV_FILE must contain the production configuration")

    expected_account_id = environ.get("EXPECTED_AWS_ACCOUNT_ID")
    if not expected_account_id:
        raise ValueError("EXPECTED_AWS_ACCOUNT_ID must identify the deployment account")

    runner_temp = Path(environ.get("RUNNER_TEMP", tempfile.gettempdir()))
    runner_temp.mkdir(parents=True, exist_ok=True)
    descriptor, config_name = tempfile.mkstemp(
        prefix="vidwiz-production-", suffix=".env", dir=runner_temp
    )
    config_path = Path(config_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as config_file:
            config_file.write(raw_config)

        settings = ProductionSettings.from_env_file(config_path)
        if settings.aws_account_id != expected_account_id:
            raise ValueError(
                "AWS_ACCOUNT_ID in LAMBDA_ENV_FILE must match EXPECTED_AWS_ACCOUNT_ID"
            )

        for secret in (
            settings.vidwiz_internal_api_admin_token.get_secret_value(),
            settings.openrouter_api_key.get_secret_value(),
        ):
            print(f"::add-mask::{secret}")

        github_environment = environ.get("GITHUB_ENV")
        if not github_environment:
            raise ValueError("GITHUB_ENV must be set by GitHub Actions")
        append_github_environment(
            Path(github_environment), "LAMBDA_ENV_FILE_PATH", str(config_path)
        )
    except Exception:
        config_path.unlink(missing_ok=True)
        raise
    return config_path


if __name__ == "__main__":
    prepare_production_config(dict(os.environ))
