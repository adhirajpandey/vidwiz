import zipfile
from pathlib import Path

import pytest

from vidwiz_infra.packaging import (
    LambdaPackage,
    asset_hash,
    create_deterministic_zip,
    validate_zip,
)


def _package(tmp_path: Path) -> LambdaPackage:
    source = tmp_path / "worker.py"
    requirements = tmp_path / "requirements.txt"
    source.write_text("def lambda_handler(event, context): return None\n")
    requirements.write_text("example==1.0 --hash=sha256:abc\n")
    return LambdaPackage("worker", source, requirements, ("example",))


def test_asset_hash_is_stable_and_covers_inputs(tmp_path: Path) -> None:
    package = _package(tmp_path)

    first = asset_hash(package)
    second = asset_hash(package)
    package.source.write_text("def lambda_handler(event, context): return event\n")

    assert first == second
    assert asset_hash(package) != first


def test_deterministic_zip_excludes_build_artifacts(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "lambda_function.py").write_text(
        "def lambda_handler(event, context): return None\n"
    )
    (stage / "dependency.py").write_text("VALUE = 1\n")
    (stage / "__pycache__").mkdir()
    (stage / "__pycache__" / "dependency.pyc").write_bytes(b"bytecode")
    (stage / "tests").mkdir()
    (stage / "tests" / "test_dependency.py").write_text("assert True\n")

    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    create_deterministic_zip(stage, first)
    create_deterministic_zip(stage, second)

    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == ["dependency.py", "lambda_function.py"]


def test_validate_zip_requires_root_handler(tmp_path: Path) -> None:
    archive_path = tmp_path / "invalid.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("nested/lambda_function.py", "pass\n")

    with pytest.raises(ValueError, match="root-level lambda_function.py"):
        validate_zip(archive_path, ())


def test_validate_zip_requires_dependencies(tmp_path: Path) -> None:
    archive_path = tmp_path / "invalid.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "lambda_function.py",
            "def lambda_handler(event, context): return None\n",
        )

    with pytest.raises(ValueError, match="required dependency"):
        validate_zip(archive_path, ("aws_lambda_powertools",))
