from pathlib import Path

import aws_cdk as cdk
import jsii
from aws_cdk import aws_lambda_python_alpha as lambda_python

from vidwiz_infra.lambda_specs import REPOSITORY_DIR

SHARED_WORKER_DIR = REPOSITORY_DIR / "backend" / "workers" / "shared"
LAMBDA_ASSET_EXCLUDES = ["tests", "__pycache__", "*.pyc"]


@jsii.implements(lambda_python.ICommandHooks)
class SharedWorkerPackageHooks:
    def before_bundling(self, input_dir: str, output_dir: str) -> list[str]:
        del input_dir, output_dir
        return []

    def after_bundling(self, input_dir: str, output_dir: str) -> list[str]:
        # Copy into the output: the input is the host source directory, so a
        # copy there lingers and nests inside itself on the next build.
        del input_dir
        return [f"cp -R /asset-shared/vidwiz_worker {output_dir}/vidwiz_worker"]


def shared_worker_bundling(source: Path) -> lambda_python.BundlingOptions:
    # The shared package is added during bundling, so the default source hash
    # would miss changes to it; hash both directories instead.
    shared_hash = cdk.FileSystem.fingerprint(
        str(SHARED_WORKER_DIR), exclude=LAMBDA_ASSET_EXCLUDES
    )
    return lambda_python.BundlingOptions(
        asset_excludes=LAMBDA_ASSET_EXCLUDES,
        asset_hash=cdk.FileSystem.fingerprint(
            str(source), exclude=LAMBDA_ASSET_EXCLUDES, extra_hash=shared_hash
        ),
        command_hooks=SharedWorkerPackageHooks(),
        volumes=[
            cdk.DockerVolume(
                host_path=str(SHARED_WORKER_DIR),
                container_path="/asset-shared",
            )
        ],
    )


def lambda_bundling() -> lambda_python.BundlingOptions:
    return lambda_python.BundlingOptions(asset_excludes=LAMBDA_ASSET_EXCLUDES)
