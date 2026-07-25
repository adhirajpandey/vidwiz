# VidWiz Production AWS Infrastructure

## Scope and Safety Boundary

`infra/` is the production-only Python CDK application for the serverless
worker system. It synthesizes the stack `vidwiz-stack` in `ap-south-1`.

Completing local validation does not authorize an AWS operation. Do not run
bootstrap, create IAM identities, deploy, copy transcripts, cut over the
Docker application, or remove legacy resources until the synthesized template
and policies have been reviewed.

The CDK stack owns:

- `vidwiz-prod`, retained if the stack is deleted or replaced.
- `vidwiz-prod-ai-note-jobs` and `vidwiz-prod-ai-summary-jobs`.
- The transcript dispatcher, AI-note worker, and AI-summary worker.
- Explicit seven-day log groups, event sources, and separate runtime roles.

The GitHub OIDC provider, `VidwizGitHubDeployRole`, and
`VidwizApplicationUser` remain manual resources outside the stack.

## Local Validation

Requirements are Python 3.13, uv, Node.js, npm, and Docker.

```text
cd infra
uv sync --locked
npm ci --ignore-scripts
uv run --locked python scripts/validate.py
```

Each Lambda source directory contains `handler.py`, `pyproject.toml`, and a
committed `uv.lock`. CDK's `PythonFunction` exports the lockfile during
bundling, installs the locked dependencies in a Lambda-compatible Docker
container, stages the ZIP assets in `cdk.out`, and publishes them during
deployment. The shared specification registry explicitly maps each source
directory, CDK construct, and physical function name; all handlers use
`handler.lambda_handler`.

The fixture is non-production data. Production synthesis uses the private
multiline GitHub secret `PRODUCTION_DEPLOYMENT_ENV`, based on
`infra/.env.example`. Its `AWS_ACCOUNT_ID` and `AWS_REGION` values are the
canonical deployment target.

Capture the existing functions' memory, timeout, runtime, architecture,
environment, event mappings, queue batch configuration, layers, and ZIPs
before filling that file.

Lambda secrets remain environment variables to avoid another paid service. The
workflow reconstructs the multiline GitHub secret as a private temporary file,
validates it, masks its individual secret values, and exposes its path through
`VIDWIZ_PRODUCTION_CONFIG_PATH` only to the CDK deployment and cleanup steps.
The same validated account and region configure OIDC, whose allowed-account
check rejects a mismatched authenticated account. CDK synthesizes those values into Lambda
configuration, so they are present in the CloudFormation template and can be
inspected by privileged AWS identities. Do not upload, cache, or print
`cdk.out`.

## Manual Preparation and Initial Deployment

Using the existing MFA-protected administrator identity:

1. Confirm the AWS account, `ap-south-1`, and global availability of
   `vidwiz-prod`.
2. Perform a modern CDK bootstrap.
3. Configure the GitHub OIDC provider.
4. Create `VidwizGitHubDeployRole` with the trust and permissions returned by
   `vidwiz_infra.manual_policies`. It trusts only the `main` branch subject and
   can assume only the deployment, file-publishing, and lookup bootstrap roles.
5. Configure the GitHub variable `AWS_GITHUB_DEPLOY_ROLE_ARN` and the secret
   `PRODUCTION_DEPLOYMENT_ENV`. Do not create a separate `AWS_ACCOUNT_ID`
   variable; account and region come from the validated secret.
6. Review the synthesized template, merge the reviewed infrastructure changes
   to `main`, then manually dispatch the AWS workflow from `main`.

Do not store `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` in GitHub.

After deployment, verify exact resource names, event mappings, notifications,
runtime settings, policies, log retention, and the absence of optional
cost-bearing resources.

## Transcript Migration and Docker Cutover

Transcript copying is intentionally manual and has no repository script.
Compare source and destination object counts, total size, representative keys,
and JSON contents. Copying `transcripts/*.json` invokes the new dispatcher and
can generate duplicate AI work and external-model cost. Before copying,
temporarily disable dispatcher processing through a reviewed infrastructure
change (for example, remove the transcript S3 notification), then restore it
after verification and manually replay the copied video IDs to the dispatcher.
Do not perform the copy with dispatcher processing enabled unless durable
idempotency has been implemented and validated.

After the copy:

1. Stop the Docker backend and helpers.
2. Manually create `VidwizApplicationUser` using the exact policy returned by
   `application_user_policy`.
3. Keep exactly one active key except briefly during rotation.
4. Configure `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` from the
   application user, `S3_TRANSCRIPT_BUCKET_NAME=vidwiz-prod`,
   `SQS_AI_NOTE_QUEUE_URL` from the stack output, and `AWS_REGION=ap-south-1`.
5. Restart and verify transcript reads/uploads, dispatch, both queues and
   workers, internal API updates, and logs.

The application user has only `GetObject`/`PutObject` on `transcripts/*` and
`SendMessage` on the AI-note queue. It cannot list the bucket, use the summary
queue, call Lambda or infrastructure APIs, manage IAM, or manage its own key.

## Manual Deployment

The AWS workflow validates and deploys in one production job only when manually
dispatched from `main`; other refs cannot deploy through the branch-scoped OIDC
role. Pull requests do not run this workflow.

Protect `main`: require pull requests and relevant checks, block force pushes
and deletion, and require zero approvals if that remains the chosen policy.
Remove any legacy permanent AWS keys from GitHub. Confirm a second unchanged
deployment has no replacement or drift.

## Recovery and Legacy Cleanup

If the initial deployment fails, keep Docker on the legacy bucket and queue,
correct the reviewed CDK/configuration issue, and manually dispatch the
workflow from `main`. If rollback retained `vidwiz-prod`, do not
rerun stack creation until CloudFormation has been reconciled with that bucket:
prepare the matching reviewed template, import the existing bucket as logical
ID `TranscriptBucket` with CloudFormation/CDK import, and verify the resulting
stack and drift state. Do not empty or delete the retained transcript bucket
as rollback.

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
