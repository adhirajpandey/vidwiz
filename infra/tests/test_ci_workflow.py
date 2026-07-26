from pathlib import Path

WORKFLOW = Path(__file__).parents[2] / ".github" / "workflows" / "ci.yml"


def workflow_text() -> str:
    return WORKFLOW.read_text()


def test_ci_runs_for_pull_requests_and_pushes_to_main_without_path_filters() -> None:
    text = workflow_text()
    trigger = text.split("permissions:", maxsplit=1)[0]

    assert "pull_request:" in trigger
    assert "push:" in trigger
    assert trigger.count("- main") == 2
    assert "paths:" not in trigger
    assert "workflow_dispatch:" not in trigger


def test_ci_uses_read_only_permissions_and_cancels_stale_runs() -> None:
    text = workflow_text()

    assert "permissions:\n  contents: read" in text
    assert "group: ${{ github.workflow }}-${{ github.ref }}" in text
    assert "cancel-in-progress: true" in text
    assert text.count("persist-credentials: false") == 3


def test_ci_has_three_parallel_quality_jobs() -> None:
    text = workflow_text()

    assert "\n  backend:\n" in text
    assert "\n  frontend:\n" in text
    assert "\n  infrastructure:\n" in text
    assert "needs:" not in text
    assert text.count("runs-on: ubuntu-latest") == 3
    assert "timeout-minutes: 15" in text
    assert "timeout-minutes: 10" in text
    assert "timeout-minutes: 30" in text


def test_backend_job_uses_locked_dependencies_and_all_quality_gates() -> None:
    text = workflow_text()

    assert "actions/checkout@v7" in text
    assert "actions/setup-python@v7" in text
    assert "astral-sh/setup-uv@v9.0.0" in text
    assert "python-version: '3.13'" in text
    assert "version: '0.8.22'" in text
    assert "cache-dependency-glob: backend/uv.lock" in text
    assert "uv sync --locked" in text
    assert "uv run --locked ruff format --check src workers" in text
    assert "uv run --locked ruff check src workers" in text
    assert "uv run --locked pytest" in text


def test_frontend_job_uses_frozen_pnpm_install_lint_and_build() -> None:
    text = workflow_text()

    assert "pnpm/action-setup@v6" in text
    assert "actions/setup-node@v7" in text
    assert "node-version: '22'" in text
    assert "cache: pnpm" in text
    assert "cache-dependency-path: frontend/pnpm-lock.yaml" in text
    assert "pnpm install --frozen-lockfile" in text
    assert "pnpm lint" in text
    assert "pnpm build" in text


def test_infrastructure_job_runs_fixture_backed_validation_without_deploying() -> None:
    text = workflow_text()

    assert "cache-dependency-glob: infra/uv.lock" in text
    assert "cache: npm" in text
    assert "cache-dependency-path: infra/package-lock.json" in text
    assert "npm ci --ignore-scripts" in text
    assert "uv run --locked python scripts/validate.py" in text
    assert "configure-aws-credentials" not in text
    assert "cdk deploy" not in text
