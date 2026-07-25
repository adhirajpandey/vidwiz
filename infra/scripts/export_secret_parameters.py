#!/usr/bin/env python3
import sys
import uuid
from pathlib import Path

INFRA_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INFRA_DIR))

from vidwiz_infra.settings import ProductionSettings  # noqa: E402


def append_environment(path: Path, name: str, value: str) -> None:
    delimiter = f"VIDWIZ_{uuid.uuid4().hex}"
    with path.open("a") as environment_file:
        environment_file.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: export_secret_parameters.py CONFIG_FILE GITHUB_ENV")
    settings = ProductionSettings.from_env_file(Path(sys.argv[1]))
    github_environment = Path(sys.argv[2])
    secrets = {
        "CFN_VIDWIZ_INTERNAL_API_ADMIN_TOKEN_VALUE": (
            settings.vidwiz_internal_api_admin_token.get_secret_value()
        ),
        "OPENROUTER_API_KEY_PARAMETER": (
            settings.openrouter_api_key.get_secret_value()
        ),
    }
    for variable, secret in secrets.items():
        print(f"::add-mask::{secret}")
        append_environment(github_environment, variable, secret)
