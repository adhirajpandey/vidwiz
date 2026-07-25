import os
from pathlib import Path

import aws_cdk as cdk

from vidwiz_infra.settings import ProductionSettings
from vidwiz_infra.stack import STACK_NAME, VidwizStack


def main() -> None:
    config_path = os.environ.get("LAMBDA_ENV_FILE_PATH")
    if not config_path:
        raise ValueError("LAMBDA_ENV_FILE_PATH must point to a validated env file")

    settings = ProductionSettings.from_env_file(Path(config_path))
    app = cdk.App()
    VidwizStack(
        app,
        STACK_NAME,
        settings=settings,
        env=cdk.Environment(
            account=settings.aws_account_id,
            region=settings.aws_region,
        ),
    )
    app.synth()


if __name__ == "__main__":
    main()
