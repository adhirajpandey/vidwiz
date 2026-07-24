#!/usr/bin/env python3
import sys
from pathlib import Path

INFRA_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(INFRA_DIR))

from vidwiz_infra.packaging import PACKAGES, package_path, validate_zip  # noqa: E402

if __name__ == "__main__":
    for package in PACKAGES:
        validate_zip(package_path(package), package.required_imports)
