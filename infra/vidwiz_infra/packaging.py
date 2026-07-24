import hashlib
import os
import shutil
import stat
import subprocess
import tempfile
import zipfile
from pathlib import Path

INFRA_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_DIR = INFRA_DIR.parent
BUILD_DIR = INFRA_DIR / "build"
BUILD_IMAGE_ID = (
    "public.ecr.aws/lambda/python:3.13@"
    "sha256:63fe2a2281147876c80e11322979a656a7a75be3d4903cef66e80ec8f9ca24c7"
)
BUILD_IMAGE = (
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


class LambdaPackage:
    def __init__(
        self,
        name: str,
        source: Path,
        requirements: Path,
        required_imports: tuple[str, ...],
    ) -> None:
        self.name = name
        self.source = source
        self.requirements = requirements
        self.required_imports = required_imports


PACKAGES = (
    LambdaPackage(
        "transcript-dispatcher",
        REPOSITORY_DIR / "backend/workers/lambdas/tasks-dispatcher.py",
        REPOSITORY_DIR / "backend/workers/lambdas/requirements/dispatcher.txt",
        ("aws_lambda_powertools", "boto3", "requests"),
    ),
    LambdaPackage(
        "ai-note-worker",
        REPOSITORY_DIR / "backend/workers/lambdas/ai-note.py",
        REPOSITORY_DIR / "backend/workers/lambdas/requirements/ai.txt",
        ("aws_lambda_powertools", "boto3", "pydantic", "requests"),
    ),
    LambdaPackage(
        "ai-summary-worker",
        REPOSITORY_DIR / "backend/workers/lambdas/ai-summary.py",
        REPOSITORY_DIR / "backend/workers/lambdas/requirements/ai.txt",
        ("aws_lambda_powertools", "boto3", "pydantic", "requests"),
    ),
)


def asset_hash(package: LambdaPackage) -> str:
    digest = hashlib.sha256()
    for label, path in (
        ("source", package.source),
        ("requirements", package.requirements),
        ("packager", Path(__file__)),
    ):
        digest.update(label.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    digest.update(BUILD_IMAGE_ID.encode())
    return digest.hexdigest()


def package_path(package: LambdaPackage) -> Path:
    return BUILD_DIR / f"{package.name}.zip"


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


def validate_zip(archive_path: Path, required_imports: tuple[str, ...]) -> None:
    if not archive_path.is_file():
        raise ValueError(f"Lambda package does not exist: {archive_path}")
    if archive_path.stat().st_size > MAX_ZIP_SIZE:
        raise ValueError(f"Lambda package exceeds 50 MiB: {archive_path}")

    try:
        with zipfile.ZipFile(archive_path) as archive:
            if archive.testzip() is not None:
                raise ValueError(f"Lambda package has corrupt members: {archive_path}")
            names = archive.namelist()
            if "lambda_function.py" not in names:
                raise ValueError(
                    "Lambda package must contain root-level lambda_function.py"
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
            for dependency in required_imports:
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
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--volume",
        f"{REPOSITORY_DIR}:/repo:ro",
        "--volume",
        f"{stage}:/asset-output",
        "--env",
        "HOME=/tmp",
    ]
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


def _install_dependencies(package: LambdaPackage, stage: Path) -> None:
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
            f"shutil.copyfile('/repo/{source}', "
            "'/asset-output/lambda_function.py')\n"
        )
        command = [
            *_docker_base(stage),
            "--entrypoint",
            "/qemu",
            BUILD_IMAGE,
            "/var/lang/bin/python3.13",
            "-c",
            python_code,
        ]
    else:
        command = [
            *_docker_base(stage),
            "--entrypoint",
            "/bin/sh",
            BUILD_IMAGE,
            "-c",
            (
                "python -m pip install --disable-pip-version-check --no-compile "
                "--no-cache-dir --require-hashes --only-binary=:all: "
                f"--target /asset-output -r /repo/{requirements} "
                f"&& cp /repo/{source} /asset-output/lambda_function.py"
            ),
        ]
    subprocess.run(command, check=True)


def _smoke_import(stage: Path) -> None:
    environment = {
        "VIDWIZ_ENDPOINT": "https://example.invalid",
        "VIDWIZ_TOKEN": "packaging-smoke-test",
        "SQS_QUEUE_URL": "https://example.invalid/note",
        "SQS_SUMMARY_QUEUE_URL": "https://example.invalid/summary",
        "S3_BUCKET_NAME": "packaging-smoke-test",
        "OPENROUTER_API_KEY": "packaging-smoke-test",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    env_args = [
        argument
        for key, value in environment.items()
        for argument in ("--env", f"{key}={value}")
    ]
    python_code = (
        "import importlib; "
        "module = importlib.import_module('lambda_function'); "
        "assert callable(getattr(module, 'lambda_handler', None))"
    )
    command = [*_docker_base(stage), *env_args, "--workdir", "/asset-output"]
    if os.environ.get("VIDWIZ_QEMU_X86_64"):
        command.extend(
            (
                "--entrypoint",
                "/qemu",
                BUILD_IMAGE,
                "/var/lang/bin/python3.13",
                "-c",
                python_code,
            )
        )
    else:
        command.extend(("--entrypoint", "python", BUILD_IMAGE, "-c", python_code))
    subprocess.run(command, check=True)


def build(package: LambdaPackage) -> Path:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=BUILD_DIR) as temporary:
        stage = Path(temporary)
        _install_dependencies(package, stage)
        _smoke_import(stage)
        output = package_path(package)
        create_deterministic_zip(stage, output)
    validate_zip(output, package.required_imports)
    return output


def build_all() -> None:
    for package in PACKAGES:
        output = build(package)
        print(f"{package.name}: {output} ({asset_hash(package)})")


def clean_build() -> None:
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
