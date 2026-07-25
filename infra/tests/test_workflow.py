from pathlib import Path

WORKFLOW = (
    Path(__file__).parents[2] / ".github" / "workflows" / "aws-infrastructure.yml"
)


def test_pull_requests_have_no_oidc_or_secret_access() -> None:
    text = WORKFLOW.read_text()
    validation = text.split("  deploy-production:", maxsplit=1)[0]

    assert "pull_request:" in validation
    assert "id-token: write" not in validation
    assert "secrets." not in validation
    assert "AWS_ACCESS_KEY_ID" not in text
    assert "AWS_SECRET_ACCESS_KEY" not in text


def test_production_runs_for_filtered_main_pushes_or_manual_dispatch() -> None:
    text = WORKFLOW.read_text()
    trigger = text.split("permissions:", maxsplit=1)[0]

    expected_paths = (
        "'infra/**'",
        "'backend/workers/lambdas/**'",
        "'.github/workflows/aws-infrastructure.yml'",
    )

    assert "workflow_dispatch:" in trigger
    assert "push:" in trigger
    assert "branches: [main]" in trigger
    assert all(trigger.count(path) == 2 for path in expected_paths)
    assert "group: vidwiz-prod-aws" in text
    assert "cancel-in-progress: false" in text
    assert "github.ref == 'refs/heads/main'" in text
    assert "github.event_name == 'push'" in text
    assert "github.event_name == 'workflow_dispatch'" in text
    assert "environment: production" not in text


def test_production_uses_oidc_and_unconditional_cleanup() -> None:
    text = WORKFLOW.read_text()

    assert "id-token: write" in text
    assert "role-to-assume:" in text
    assert "allowed-account-ids:" in text
    assert "if: always()" in text
    assert 'rm -- "${CONFIG_FILE}"' in text
    assert (
        "VidwizInternalApiAdminToken=${CFN_VIDWIZ_INTERNAL_API_ADMIN_TOKEN_VALUE}"
    ) in text
    assert "VIDWIZ_TOKEN_PARAMETER" not in text


def test_workflow_uses_cdk_managed_lambda_bundling() -> None:
    text = WORKFLOW.read_text()

    assert "scripts/build_lambdas.py" not in text
    assert "scripts/validate_lambdas.py" not in text
    assert "npx cdk synth vidwiz-stack --quiet --output cdk.out" in text
    assert "npx cdk deploy --app cdk.out vidwiz-stack" in text
