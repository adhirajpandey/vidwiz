import aws_cdk as cdk
import jsii
from aws_cdk import aws_lambda_python_alpha as lambda_python

from vidwiz_infra.lambda_specs import REPOSITORY_DIR

SHARED_WORKER_DIR = REPOSITORY_DIR / "backend" / "workers" / "shared"


@jsii.implements(lambda_python.ICommandHooks)
class SharedWorkerPackageHooks:
    def before_bundling(self, input_dir: str, output_dir: str) -> list[str]:
        del output_dir
        return [f"cp -R /asset-shared/vidwiz_worker {input_dir}/vidwiz_worker"]

    def after_bundling(self, input_dir: str, output_dir: str) -> list[str]:
        del input_dir, output_dir
        return []


def shared_worker_bundling() -> lambda_python.BundlingOptions:
    return lambda_python.BundlingOptions(
        command_hooks=SharedWorkerPackageHooks(),
        volumes=[
            cdk.DockerVolume(
                host_path=str(SHARED_WORKER_DIR),
                container_path="/asset-shared",
            )
        ],
    )
