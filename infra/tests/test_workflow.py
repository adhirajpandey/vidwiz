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


def test_production_is_manual_only_and_serialized() -> None:
    text = WORKFLOW.read_text()
    trigger = text.split("permissions:", maxsplit=1)[0]

    assert "workflow_dispatch:" in trigger
    assert "push:" not in trigger
    assert "group: vidwiz-prod-aws" in text
    assert "cancel-in-progress: false" in text
    assert "github.event_name == 'workflow_dispatch'" in text


def test_production_uses_oidc_and_unconditional_cleanup() -> None:
    text = WORKFLOW.read_text()

    assert "id-token: write" in text
    assert "role-to-assume:" in text
    assert "allowed-account-ids:" in text
    assert "if: always()" in text
    assert 'rm -- "${CONFIG_FILE}"' in text
