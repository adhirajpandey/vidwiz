import ast
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path

from vidwiz_infra.lambda_specs import (
    INFRA_DIR,
    LAMBDA_SPECS,
    REPOSITORY_DIR,
    LambdaSpec,
)

BUILD_DIR = INFRA_DIR / "build"
LAMBDA_BUILD_IMAGE = (
    "public.ecr.aws/lambda/python@"
    "sha256:f9adc52cc2242e7cb02c7ba2dfb9c200ac7010c5bbcd98f312be6140e71a9ab3"
)
MAX_ZIP_SIZE = 50 * 1024 * 1024
MAX_UNZIPPED_SIZE = 250 * 1024 * 1024
EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "test",
    "tests",
    "venv",
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_hash(package: LambdaSpec) -> str:
    digest = hashlib.sha256()
    for path in sorted(package.source.rglob("*")):
        if not path.is_file() or _is_excluded(path, package.source):
            continue
        relative = path.relative_to(package.source).as_posix()
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def input_hashes(package: LambdaSpec) -> dict[str, str]:
    return {
        "source": _source_hash(package),
        "requirements": file_hash(package.requirements),
        "packager": file_hash(Path(__file__)),
        "specifications": file_hash(INFRA_DIR / "vidwiz_infra/lambda_specs.py"),
    }


def asset_hash(package: LambdaSpec) -> str:
    inputs = {**input_hashes(package), "build_image": LAMBDA_BUILD_IMAGE}
    return hashlib.sha256(
        json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def package_path(package: LambdaSpec) -> Path:
    return BUILD_DIR / f"{package.artifact_stem}.zip"


def manifest_path(package: LambdaSpec) -> Path:
    return package_path(package).with_suffix(".zip.manifest.json")


def artifact_manifest(package: LambdaSpec, archive_path: Path) -> dict[str, str]:
    return {
        **input_hashes(package),
        "build_image": LAMBDA_BUILD_IMAGE,
        "asset_hash": asset_hash(package),
        "artifact_hash": file_hash(archive_path),
    }


def write_manifest(package: LambdaSpec, archive_path: Path) -> Path:
    destination = manifest_path(package)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(artifact_manifest(package, archive_path), sort_keys=True) + "\n"
    )
    temporary.replace(destination)
    return destination


def validate_artifact(package: LambdaSpec) -> Path:
    archive_path = package_path(package)
    validate_zip(archive_path, package)
    manifest = manifest_path(package)
    if not manifest.is_file():
        raise ValueError(f"Lambda package manifest does not exist: {manifest}")
    try:
        recorded = json.loads(manifest.read_text())
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid Lambda package manifest: {manifest}") from error
    expected = artifact_manifest(package, archive_path)
    if recorded != expected:
        raise ValueError(
            f"Lambda package manifest does not match current inputs: {manifest}; "
            "run `uv run python scripts/build_lambdas.py`"
        )
    return archive_path


def _is_excluded(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return any(part in EXCLUDED_PARTS for part in relative.parts) or (
        path.suffix in {".pyc", ".pyo"}
    )


def create_deterministic_zip(stage: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".zip.tmp")
    temporary.unlink(missing_ok=True)

    files = sorted(
        path
        for path in stage.rglob("*")
        if path.is_file() and not _is_excluded(path, stage)
    )
    with zipfile.ZipFile(
        temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in files:
            relative = path.relative_to(stage).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            mode = stat.S_IMODE(path.stat().st_mode)
            info.external_attr = (mode or 0o644) << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)
    temporary.replace(destination)


def validate_zip(archive_path: Path, package: LambdaSpec) -> None:
    if not archive_path.is_file():
        raise ValueError(f"Lambda package does not exist: {archive_path}")
    if archive_path.stat().st_size > MAX_ZIP_SIZE:
        raise ValueError(f"Lambda package exceeds 50 MiB: {archive_path}")

    try:
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip() is not None:
                raise ValueError(f"Lambda package has corrupt members: {archive_path}")
            names = archive.namelist()
            module_name, function_name = package.handler.rsplit(".", maxsplit=1)
            handler_path = f"{module_name.replace('.', '/')}.py"
            if handler_path not in names:
                raise ValueError(f"Lambda package must contain {handler_path}")
            handler_source = archive.read(handler_path).decode()
            handler_tree = ast.parse(handler_source, filename=handler_path)
            if not any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == function_name
                for node in handler_tree.body
            ):
                raise ValueError(
                    f"Lambda package handler is not callable: {package.handler}"
                )
            if any(
                part in EXCLUDED_PARTS or name.endswith((".pyc", ".pyo"))
                for name in names
                for part in Path(name).parts
            ):
                raise ValueError("Lambda package contains excluded build artifacts")
            size = sum(item.file_size for item in archive.infolist())
            if size > MAX_UNZIPPED_SIZE:
                raise ValueError(f"Lambda package exceeds 250 MiB: {archive_path}")
            for dependency in package.required_imports:
                module = f"{dependency}.py"
                package_prefix = f"{dependency}/"
                if module not in names and not any(
                    name.startswith(package_prefix) for name in names
                ):
                    raise ValueError(
                        f"Lambda package is missing required dependency: {dependency}"
                    )
    except zipfile.BadZipFile as error:
        raise ValueError(f"Invalid Lambda ZIP: {archive_path}") from error


def _docker_base(stage: Path) -> list[str]:
    command = [
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--volume",
        f"{REPOSITORY_DIR}:/repo:ro",
        "--volume",
        f"{stage}:/asset-output",
        "--env",
        "HOME=/tmp",
    ]
    getuid = getattr(os, "getuid", None)
    getgid = getattr(os, "getgid", None)
    if callable(getuid) and callable(getgid):
        command[5:5] = ["--user", f"{getuid()}:{getgid()}"]
    qemu_path = os.environ.get("VIDWIZ_QEMU_X86_64")
    if qemu_path:
        command.extend(
            (
                "--volume",
                f"{Path(qemu_path).resolve()}:/qemu:ro",
                "--env",
                "QEMU_CPU=max",
            )
        )
    return command


def _install_dependencies(package: LambdaSpec, stage: Path) -> None:
    requirements = package.requirements.relative_to(REPOSITORY_DIR).as_posix()
    source = package.source.relative_to(REPOSITORY_DIR).as_posix()
    pip_arguments = [
        "pip",
        "install",
        "--disable-pip-version-check",
        "--no-compile",
        "--no-cache-dir",
        "--require-hashes",
        "--only-binary=:all:",
        "--target",
        "/asset-output",
        "-r",
        f"/repo/{requirements}",
    ]
    if os.environ.get("VIDWIZ_QEMU_X86_64"):
        python_code = (
            "import runpy, shutil, sys\n"
            f"sys.argv = {pip_arguments!r}\n"
            "try:\n"
            "    runpy.run_module('pip', run_name='__main__')\n"
            "except SystemExit as error:\n"
            "    if error.code:\n"
            "        raise\n"
            f"shutil.copytree('/repo/{source}', "
            "'/asset-output', dirs_exist_ok=True)\n"
        )
        command = [
            *_docker_base(stage),
            "--entrypoint",
            "/qemu",
            LAMBDA_BUILD_IMAGE,
            "/var/lang/bin/python3.13",
            "-c",
            python_code,
        ]
    else:
        command = [
            *_docker_base(stage),
            "--entrypoint",
            "/bin/sh",
            LAMBDA_BUILD_IMAGE,
            "-c",
            (
                "python -m pip install --disable-pip-version-check --no-compile "
                "--no-cache-dir --require-hashes --only-binary=:all: "
                f"--target /asset-output -r /repo/{requirements} "
                f"&& cp -R /repo/{source}/. /asset-output/"
            ),
        ]
    subprocess.run(command, check=True)


def _smoke_import(package: LambdaSpec, stage: Path) -> None:
    environment = {
        "VIDWIZ_INTERNAL_API_BASE_URL": "https://example.invalid",
        "VIDWIZ_INTERNAL_API_ADMIN_TOKEN": "packaging-smoke-test",
        "SQS_AI_NOTE_QUEUE_URL": "https://example.invalid/note",
        "SQS_AI_SUMMARY_QUEUE_URL": "https://example.invalid/summary",
        "S3_TRANSCRIPT_BUCKET_NAME": "packaging-smoke-test",
        "OPENROUTER_API_KEY": "packaging-smoke-test",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    env_args = [
        argument
        for key, value in environment.items()
        for argument in ("--env", f"{key}={value}")
    ]
    module_name, function_name = package.handler.rsplit(".", maxsplit=1)
    python_code = (
        "import importlib; "
        f"module = importlib.import_module({module_name!r}); "
        f"assert callable(getattr(module, {function_name!r}, None))"
    )
    command = [*_docker_base(stage), *env_args, "--workdir", "/asset-output"]
    if os.environ.get("VIDWIZ_QEMU_X86_64"):
        command.extend(
            (
                "--entrypoint",
                "/qemu",
                LAMBDA_BUILD_IMAGE,
                "/var/lang/bin/python3.13",
                "-c",
                python_code,
            )
        )
    else:
        command.extend(
            ("--entrypoint", "python", LAMBDA_BUILD_IMAGE, "-c", python_code)
        )
    subprocess.run(command, check=True)


def build(package: LambdaSpec) -> Path:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=BUILD_DIR) as temporary:
        stage = Path(temporary)
        _install_dependencies(package, stage)
        _smoke_import(package, stage)
        output = package_path(package)
        create_deterministic_zip(stage, output)
    validate_zip(output, package)
    write_manifest(package, output)
    return output


def build_all() -> None:
    for package in LAMBDA_SPECS:
        output = build(package)
        print(f"{package.key}: {output} ({asset_hash(package)})")


def clean_build() -> None:
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
