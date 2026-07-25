import zipfile
from pathlib import Path

import pytest

from vidwiz_infra.lambda_specs import LAMBDA_SPECS, LambdaSpec
from vidwiz_infra.packaging import (
    _smoke_import,
    asset_hash,
    create_deterministic_zip,
    manifest_path,
    package_path,
    validate_artifact,
    validate_zip,
    write_manifest,
)


def _package(tmp_path: Path) -> LambdaSpec:
    source = tmp_path / "worker"
    source.mkdir()
    (source / "handler.py").write_text(
        "def lambda_handler(event, context): return None\n"
    )
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("example==1.0 --hash=sha256:abc\n")
    return LambdaSpec(
        key="worker",
        artifact_stem="worker",
        construct_id="Worker",
        function_name="vidwiz-prod-worker",
        source=source,
        requirements=requirements,
        required_imports=("example",),
    )


def _write_valid_archive(archive_path: Path) -> None:
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "handler.py",
            "def lambda_handler(event, context): return None\n",
        )
        archive.writestr("example.py", "VALUE = 1\n")


def test_asset_hash_is_stable_and_covers_every_source_file(tmp_path: Path) -> None:
    package = _package(tmp_path)

    first = asset_hash(package)
    assert asset_hash(package) == first

    (package.source / "helper.py").write_text("VALUE = 1\n")
    assert asset_hash(package) != first


def test_deterministic_zip_excludes_build_artifacts(tmp_path: Path) -> None:
    stage = tmp_path / "stage"
    stage.mkdir()
    (stage / "handler.py").write_text(
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
        assert archive.namelist() == ["dependency.py", "handler.py"]
        assert "lambda_function.py" not in archive.namelist()


def test_validate_zip_requires_the_declared_root_handler(tmp_path: Path) -> None:
    package = _package(tmp_path)
    archive_path = tmp_path / "invalid.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("nested/handler.py", "pass\n")

    with pytest.raises(ValueError, match="must contain handler.py"):
        validate_zip(archive_path, package)


def test_validate_zip_requires_a_callable_handler(tmp_path: Path) -> None:
    package = _package(tmp_path)
    archive_path = tmp_path / "invalid.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("handler.py", "lambda_handler = None\n")

    with pytest.raises(ValueError, match="handler is not callable"):
        validate_zip(archive_path, package)


def test_validate_zip_requires_dependencies(tmp_path: Path) -> None:
    package = _package(tmp_path)
    archive_path = tmp_path / "invalid.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "handler.py",
            "def lambda_handler(event, context): return None\n",
        )

    with pytest.raises(ValueError, match="required dependency"):
        validate_zip(archive_path, package)


def test_smoke_import_uses_the_declared_handler(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = _package(tmp_path)
    commands: list[list[str]] = []

    monkeypatch.setattr(
        "vidwiz_infra.packaging.subprocess.run",
        lambda command, check: commands.append(command),
    )
    monkeypatch.setattr(
        "vidwiz_infra.packaging._docker_base",
        lambda stage: ["docker"],
    )

    _smoke_import(package, tmp_path)

    command = commands[0]
    python_code = command[command.index("-c") + 1]
    assert "import_module('handler')" in python_code
    assert "getattr(module, 'lambda_handler'" in python_code


def test_lambda_spec_registry_has_explicit_unique_mappings() -> None:
    assert len(LAMBDA_SPECS) == 3
    assert len({spec.key for spec in LAMBDA_SPECS}) == len(LAMBDA_SPECS)
    assert {
        (
            spec.key,
            spec.artifact_stem,
            spec.construct_id,
            spec.function_name,
            spec.handler,
        )
        for spec in LAMBDA_SPECS
    } == {
        (
            "transcript_dispatcher",
            "transcript_dispatcher",
            "TranscriptDispatcher",
            "vidwiz-prod-transcript-dispatcher",
            "handler.lambda_handler",
        ),
        (
            "ai_note_worker",
            "ai_note_worker",
            "AiNoteWorker",
            "vidwiz-prod-ai-note-worker",
            "handler.lambda_handler",
        ),
        (
            "ai_summary_worker",
            "ai_summary_worker",
            "AiSummaryWorker",
            "vidwiz-prod-ai-summary-worker",
            "handler.lambda_handler",
        ),
    }


def test_validate_artifact_requires_a_manifest_matching_current_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = _package(tmp_path)
    archive_path = tmp_path / "worker.zip"
    monkeypatch.setattr("vidwiz_infra.packaging.BUILD_DIR", tmp_path)
    _write_valid_archive(archive_path)
    write_manifest(package, archive_path)
    assert manifest_path(package).is_file()
    assert validate_artifact(package) == package_path(package)

    (package.source / "handler.py").write_text(
        "def lambda_handler(event, context): return event\n"
    )

    with pytest.raises(ValueError, match="does not match current inputs"):
        validate_artifact(package)


def test_validate_artifact_rejects_a_changed_zip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = _package(tmp_path)
    archive_path = tmp_path / "worker.zip"
    monkeypatch.setattr("vidwiz_infra.packaging.BUILD_DIR", tmp_path)
    _write_valid_archive(archive_path)
    write_manifest(package, archive_path)
    with zipfile.ZipFile(archive_path, "a") as archive:
        archive.writestr("unexpected.py", "VALUE = 2\n")

    with pytest.raises(ValueError, match="does not match current inputs"):
        validate_artifact(package)
