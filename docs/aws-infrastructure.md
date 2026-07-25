# VidWiz Production AWS Infrastructure

## Scope and Safety Boundary

`infra/` is the production-only Python CDK application for the serverless
worker system. It synthesizes the stack `vidwiz-stack` in `ap-south-1`.

Completing local validation does not authorize an AWS operation. Do not run
bootstrap, create IAM identities, deploy, copy transcripts, cut over the
Docker application, or remove legacy resources until the synthesized template
and policies have been reviewed.

The CDK stack owns:

- `vidwiz-prod-transcripts`, retained if the stack is deleted or replaced.
- `vidwiz-prod-ai-note-jobs` and `vidwiz-prod-ai-summary-jobs`.
- The transcript dispatcher, AI-note worker, and AI-summary worker.
- Explicit seven-day log groups, event sources, and separate runtime roles.

The GitHub OIDC provider, `VidwizGitHubDeployRole`, and
`VidwizApplicationUser` remain manual resources outside the stack.

## Local Validation

Requirements are Python 3.13, uv, Node.js, npm, and Docker.

```text
cd infra
uv sync --frozen
npm ci --ignore-scripts
uv run ruff format --check app.py vidwiz_infra scripts tests
uv run ruff check app.py vidwiz_infra scripts tests
uv run mypy app.py vidwiz_infra scripts tests
uv run pytest
uv run python scripts/build_lambdas.py
uv run python scripts/validate_lambdas.py
LAMBDA_ENV_FILE_PATH=tests/fixtures/production.env npx cdk synth vidwiz-stack
```

Each Lambda ZIP is accompanied by a generated `.zip.manifest.json` file. CDK
validates its source, requirements, packager, build-image, and ZIP hashes
before accepting the ZIP, so rebuild the artifacts after changing any of those
inputs.

The shared Lambda specification registry explicitly maps each source
directory, artifact, CDK construct, physical function name, requirements file,
and `handler.lambda_handler` entry point. Each source directory is flattened
into its own ZIP root; the stack never infers an artifact from a function name.

The fixture is non-production data. Production synthesis uses the private
multiline GitHub secret `LAMBDA_ENV_FILE`, based on `infra/.env.example`.
Capture the existing functions' memory, timeout, runtime, architecture,
environment, event mappings, queue batch configuration, layers, and ZIPs
before filling that file.

Lambda secrets remain environment variables to avoid another paid service.
They enter CloudFormation through `NoEcho` parameters and are absent from the
synthesized template, but privileged AWS identities can still inspect Lambda
configuration.

## Manual Preparation and Initial Deployment

Using the existing MFA-protected administrator identity:

1. Confirm the AWS account, `ap-south-1`, and global availability of
   `vidwiz-prod-transcripts`.
2. Perform a modern CDK bootstrap.
3. Configure the GitHub OIDC provider.
4. Create `VidwizGitHubDeployRole` with the trust and permissions returned by
   `vidwiz_infra.manual_policies`. It trusts only the `main` branch subject and
   can assume only the deployment, file-publishing, and lookup bootstrap roles.
5. Configure GitHub variables `AWS_ACCOUNT_ID` and
   `AWS_GITHUB_DEPLOY_ROLE_ARN`, plus the secret `LAMBDA_ENV_FILE`.
6. Review the synthesized template, then merge the reviewed infrastructure
   changes to `main` or manually dispatch the AWS workflow from `main`.

Do not store `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` in GitHub.

After deployment, verify exact resource names, event mappings, notifications,
runtime settings, policies, log retention, and the absence of optional
cost-bearing resources.

## Transcript Migration and Docker Cutover

Transcript copying is intentionally manual and has no repository script.
Compare source and destination object counts, total size, representative keys,
and JSON contents. Copying `transcripts/*.json` invokes the new dispatcher, so
stop the Docker application or accept idempotent duplicate submissions.

After the copy:

1. Stop the Docker backend and helpers.
2. Manually create `VidwizApplicationUser` using the exact policy returned by
   `application_user_policy`.
3. Keep exactly one active key except briefly during rotation.
4. Configure `S3_TRANSCRIPT_BUCKET_NAME=vidwiz-prod-transcripts`,
   `SQS_AI_NOTE_QUEUE_URL` from the stack output, and
   `AWS_REGION=ap-south-1`.
5. Restart and verify transcript reads/uploads, dispatch, both queues and
   workers, internal API updates, and logs.

The application user has only `GetObject`/`PutObject` on `transcripts/*` and
`SendMessage` on the AI-note queue. It cannot list the bucket, use the summary
queue, call Lambda or infrastructure APIs, manage IAM, or manage its own key.

## Automatic Deployment

The AWS workflow deploys after validation when a push to `main` changes
`infra/**`, `backend/workers/lambdas/**`, or the workflow itself. It can also
be manually dispatched from `main`; other refs cannot deploy through the
branch-scoped OIDC role.

Protect `main`: require pull requests and infrastructure validation, block
   force pushes and deletion, and require zero approvals if that remains the
   chosen policy.
Remove any legacy permanent AWS keys from GitHub. Confirm a second unchanged
deployment has no replacement or drift.

## Recovery and Legacy Cleanup

If the initial deployment fails, keep Docker on the legacy bucket and queue,
correct the reviewed CDK/configuration issue, and re-run the failed job or
manually dispatch the workflow from `main`.
Do not empty or delete the retained transcript bucket as rollback.

If cutover fails, stop the application, restore the previous Docker
configuration and credential, restart it, and verify the legacy path before
investigating. The accepted downtime window avoids dual-write complexity.

Only after full acceptance, manually remove old event mappings, functions,
queues, execution roles and policies, log groups, Docker credentials, and the
old transcript bucket after final data verification. The new transcript bucket
is retained and is never routine cleanup.

Rotate the Docker application key by creating a temporary replacement,
updating and restarting the host, verifying it, deleting the former key, and
returning to exactly one active key.
