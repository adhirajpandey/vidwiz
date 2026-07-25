from pathlib import Path

WORKFLOW = (
    Path(__file__).parents[2] / ".github" / "workflows" / "aws-infrastructure.yml"
)


def test_production_runs_for_filtered_main_pushes_or_manual_dispatch() -> None:
    text = WORKFLOW.read_text()
    trigger = text.split("permissions:", maxsplit=1)[0]

    assert "workflow_dispatch:" in trigger
    assert "push:" in trigger
    assert "branches: [main]" in trigger
    assert "pull_request:" not in trigger
    for path in (
        "'infra/**'",
        "'backend/workers/lambdas/**'",
        "'.github/workflows/aws-infrastructure.yml'",
    ):
        assert trigger.count(path) == 1


def test_production_job_keeps_branch_oidc_and_serial_deployments() -> None:
    text = WORKFLOW.read_text()

    assert "if: github.ref == 'refs/heads/main'" in text
    assert "environment: production" not in text
    assert "timeout-minutes: 30" in text
    assert "group: vidwiz-prod-aws" in text
    assert "cancel-in-progress: false" in text
    assert "id-token: write" in text
    assert "role-to-assume:" in text
    assert "role-session-name: vidwiz-${{ github.run_id }}" in text
    assert "allowed-account-ids:" in text
    assert "AWS_ACCESS_KEY_ID" not in text
    assert "AWS_SECRET_ACCESS_KEY" not in text


def test_workflow_uses_major_action_versions_and_locked_dependency_caches() -> None:
    text = WORKFLOW.read_text()

    for action in (
        "actions/checkout@v4",
        "actions/setup-python@v6",
        "astral-sh/setup-uv@v8",
        "actions/setup-node@v6",
        "aws-actions/configure-aws-credentials@v6",
    ):
        assert action in text
    assert "enable-cache: true" in text
    assert "cache-dependency-glob: infra/uv.lock" in text
    assert "cache: npm" in text
    assert "cache-dependency-path: infra/package-lock.json" in text
    assert "uv sync --frozen" in text
    assert "npm ci --ignore-scripts" in text


def test_workflow_uses_repository_scripts_and_parameter_free_deployment() -> None:
    text = WORKFLOW.read_text()

    assert "uv run python scripts/validate.py" in text
    assert "uv run python scripts/prepare_production_config.py" in text
    assert "npm exec -- cdk deploy vidwiz-stack --require-approval never" in text
    assert "--parameters" not in text
    assert "cdk synth" not in text
    assert "export_secret_parameters.py" not in text
    assert "aws cloudformation describe-stacks" not in text
    assert "aws lambda get-function-configuration" not in text


def test_workflow_cleans_up_the_temporary_production_configuration() -> None:
    text = WORKFLOW.read_text()

    assert "if: always()" in text
    assert "CONFIG_FILE: ${{ env.LAMBDA_ENV_FILE_PATH }}" in text
    assert (
        "uv run python scripts/prepare_production_config.py --cleanup" in text
    )
    assert 'rm -- "${CONFIG_FILE}"' not in text
