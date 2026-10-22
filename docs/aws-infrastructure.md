# VidWiz Production AWS Infrastructure

## Scope and Safety Boundary

`infra/` is the production-only Python CDK application for the serverless
worker system. It synthesizes the stack `vidwiz-v3-stack` in `ap-south-1`.

Completing local validation does not authorize an AWS operation. Do not run
bootstrap, create IAM identities, or deploy until the synthesized template and
policies have been reviewed.

The CDK stack owns:

- `vidwiz-v3-transcripts`, retained if the stack is deleted or replaced.
- `vidwiz-v3-ai-note-jobs` and `vidwiz-v3-ai-summary-jobs`, each with a
  dead-letter queue (`vidwiz-v3-ai-note-dlq`, `vidwiz-v3-ai-summary-dlq`) that
  receives a job after three failed attempts.
- The transcript dispatcher, AI-note worker, and AI-summary worker.
- Explicit seven-day log groups, event sources, and separate runtime roles.

The GitHub OIDC provider, `VidwizGitHubDeployRole`, and the application user
remain manual resources outside the stack.

## Local Validation

Requirements are Python 3.13, uv, Node.js, npm, and Docker.

```text
cd infra
uv sync --locked
npm ci --ignore-scripts
uv run --locked python scripts/validate.py
```

Each Lambda source directory contains `handler.py`, a domain-specific service
module, colocated tests, `pyproject.toml`, and a committed `uv.lock`. CDK's
`PythonFunction` excludes tests and Python bytecode caches, exports the
lockfile during bundling, installs the locked dependencies in a
Lambda-compatible Docker container, stages the ZIP assets in `cdk.out`, and
publishes them during deployment. The shared specification registry explicitly
maps each source directory, service file, CDK construct, and physical function
name; all handlers use `handler.lambda_handler`. The two AI worker assets also
include the shared `vidwiz_worker` package.

The fixture is non-production data. Production synthesis uses the private
multiline GitHub secret `PRODUCTION_DEPLOYMENT_ENV`, based on
`infra/.env.example`. Its `AWS_ACCOUNT_ID` and `AWS_REGION` values are the
canonical deployment target.

The AI worker models are independently configurable. `SUMMARY_MODEL` defaults
to `qwen/qwen3.5-35b-a3b`, and `AI_NOTE_MODEL` defaults to
`z-ai/glm-5.3-flash`. The application configures Wiz chat separately through
`WIZ_MODEL`, which defaults to `minimax/minimax-m2.5`.

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

Using an MFA-protected administrator identity:

1. Confirm the AWS account, `ap-south-1`, and global availability of
   `vidwiz-v3-transcripts`.
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

## Application User

The Docker application reaches AWS through one manually managed IAM user:

1. Create it with the exact policy returned by `application_user_policy`.
2. Keep exactly one active key except briefly during rotation.
3. Configure `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` from that user,
   `S3_TRANSCRIPT_BUCKET_NAME=vidwiz-v3-transcripts`, `SQS_AI_NOTE_QUEUE_URL`
   and `SQS_AI_SUMMARY_QUEUE_URL` from the stack outputs, and
   `AWS_REGION=ap-south-1`.
4. Restart and verify transcript reads/uploads, dispatch, both queues and
   workers, internal API updates, and logs.

The application user has only `GetObject`/`PutObject` on `transcripts/*` and
`SendMessage` on the job queues. It cannot list the bucket, call Lambda or
infrastructure APIs, manage IAM, or manage its own key.

## Manual Deployment

The AWS workflow validates and deploys in one production job only when manually
dispatched from `main`; other refs cannot deploy through the branch-scoped OIDC
role. Pull requests do not run this workflow.

Protect `main`: require pull requests and relevant checks, block force pushes
and deletion, and require zero approvals if that remains the chosen policy.
Confirm a second unchanged deployment has no replacement or drift.

## Recovery

If a deployment fails, correct the reviewed CDK or configuration issue and
manually dispatch the workflow from `main` again. If a failed stack creation
retained `vidwiz-v3-transcripts`, do not rerun stack creation until
CloudFormation has been reconciled with that bucket: prepare the matching
reviewed template, import the existing bucket as logical ID `TranscriptBucket`
with CloudFormation/CDK import, and verify the resulting stack and drift state.
Do not empty or delete the transcript bucket as rollback. It is never routine
cleanup.

Rotate the Docker application key by creating a temporary replacement,
updating and restarting the host, verifying it, deleting the former key, and
returning to exactly one active key.
