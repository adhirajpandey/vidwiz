# AWS Deployment and Worker Follow-up Findings

## Purpose

This document is the current follow-up record for VidWiz's AWS serverless
workers and the Docker-hosted API/helpers. It was reconciled with `main` on
2026-07-26, including the commits that standardised production configuration,
consolidated the environment template, removed the obsolete backend deployment
workflow, and aligned the Docker image with Python 3.13.

It is not authorization to deploy, migrate transcripts, create IAM resources,
or change production credentials.

## Current Deployment Shape

```text
GitHub Actions (manual, main only)
  -> GitHub OIDC deploy role
  -> CDK bootstrap roles
  -> vidwiz-stack
       -> transcript S3 bucket -> transcript dispatcher
       -> AI-note SQS -> AI-note Lambda
       -> AI-summary SQS -> AI-summary Lambda

Docker Compose host
  -> FastAPI API + PostgreSQL + transcript helper + metadata helper
  -> S3 transcript bucket and AI-note SQS using application credentials
```

`infra/` owns the production serverless resources. The GitHub OIDC provider,
GitHub deployment role, and Docker application's IAM identity remain manual
bootstrap resources. Compose owns the API, database, and helper definitions;
there is currently no repository-managed GitHub Actions workflow that deploys
the Docker host.

## Recent Improvements Confirmed

| Area | Current state |
|---|---|
| Lambda packaging | Complete. Each Lambda has an explicit source directory, `pyproject.toml`, and locked dependencies; CDK `PythonFunction` bundles the reviewed source. |
| Production config names | Complete. `PRODUCTION_DEPLOYMENT_ENV`, `VIDWIZ_PRODUCTION_CONFIG_PATH`, and `ProductionDeploymentConfig` replace the ambiguous Lambda-specific names. |
| Deployment target | Complete. Account and region are parsed from the validated production configuration and used for OIDC's allowed-account check and CDK. |
| Ambient config override | Complete. The explicit deployment file is parsed directly and is covered by a regression test that rejects ambient overrides. |
| Backend deployment ownership | Improved. The obsolete workflow that both ran Compose helpers and restarted systemd helpers was removed. Do not reintroduce a second helper supervisor without an explicit ownership decision. |
| Environment template | Improved. The single root `.env.example` now documents Compose, API, helper, and optional integration settings. |
| Runtime alignment | Improved. The backend Docker image now uses Python 3.13, matching the current project tooling and Lambda runtime. |

The infrastructure unit suite verifies these completed contracts. A real CDK
synthesis still requires Docker because `PythonFunction` bundles each Lambda in
a Lambda-compatible container.

## Open Findings

### P0: Lambda failures can be acknowledged and lost

The AI-note and AI-summary handlers catch per-message exceptions and continue.
With the current SQS event mappings (`batch_size=1` and
`report_batch_item_failures=False`), a normal handler return acknowledges the
message even when fetching a transcript, calling OpenRouter, or persisting the
result failed.

The dispatcher has the same acknowledgement problem for S3-triggered work. It
also processes only `Records[0]`, does not URL-decode S3 object keys, and logs
partial SQS batch failures without making the invocation fail.

Required change:

1. Process every S3 record and URL-decode each key before deriving the video
   ID.
2. Classify malformed input and permanent business rejections separately from
   retriable infrastructure/provider errors.
3. Raise retriable errors from batch-size-one handlers. If batches grow, use
   Lambda partial-batch responses and Powertools Batch Processor.
4. Add a dead-letter queue and redrive policy to each source queue, including
   alerting and a documented replay procedure.
5. Add regression tests for multi-record S3 events, SQS send partial failures,
   retriable handler failures, and DLQ configuration.

SQS/Lambda delivery is at least once, and AWS recommends idempotent handlers,
redrive policies, and partial-batch responses where applicable. See [Using
Lambda with SQS](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html)
and [SQS error handling](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-errorhandling.html).

### P0: There is no durable idempotency boundary for AI work

S3 notifications and SQS deliveries can be duplicated. Repeated dispatcher
invocations can enqueue the same empty AI note again before the worker updates
it; the summary's read-before-write check has the same race. This can generate
duplicate model calls and cost even when the final database value is harmless.

Use the existing PostgreSQL-backed API as the source of truth. Introduce an
async job record, or equivalent atomic claim state, keyed by job type, entity,
and transcript/input version. The dispatcher should enqueue a `job_id`; a
worker should atomically claim, complete, or fail that job through the internal
API. This provides idempotency, retries, replay, status visibility, and cost
attribution without introducing DynamoDB only for Lambda idempotency.

### P1: Lambda secrets still enter CloudFormation and Lambda environment configuration

The multiline production configuration is intentionally a single GitHub secret
that contains deployment target, sizing, non-secret runtime settings, and two
runtime secrets. CDK materializes the internal API token and OpenRouter key in
the Lambda environment configuration. This is an accepted migration tradeoff,
but privileged CloudFormation and Lambda identities can inspect those values.

For the next security-focused change:

- Keep deployment identity, account, region, resource names, and tuning values
  as typed non-secret configuration.
- Store API keys and authorization tokens in AWS Secrets Manager; use a
  narrowly scoped runtime role and cached retrieval through Powertools.
- Use SSM Parameter Store for simple non-secret configuration that must be
  changed without code deployment; use AppConfig only for genuinely dynamic
  operational controls.
- Keep GitHub secrets limited to the values required to deploy, not every
  runtime secret where AWS can become the source of truth.

AWS recommends Secrets Manager rather than Lambda environment variables for
API keys and authorization tokens. See [Use Secrets Manager secrets in Lambda
functions](https://docs.aws.amazon.com/lambda/latest/dg/with-secrets-manager.html).

### P1: Docker Compose exposes the complete environment to every service

The API, both helpers, and PostgreSQL all import the same `.env` file. This
gives the database and helpers secrets and payment configuration they do not
need. The consolidated template is easier to discover, but it is not a least-
privilege runtime contract.

Retain one human-maintained template if desired, but project only the required
keys into each Compose service. The intended ownership is:

| Consumer | Required configuration scope |
|---|---|
| PostgreSQL | `POSTGRES_*` only |
| API | database, auth, payments, logging, S3/SQS, Wiz/OpenRouter |
| Transcript/metadata helpers | internal API base URL and internal API credential only |
| Lambda dispatcher | internal API credential and queue URLs |
| AI-note/summary Lambdas | transcript bucket, internal API credential, OpenRouter, and worker tuning |

The API currently requires static AWS access keys at startup. Continue to use
the present narrowly scoped application identity during the migration, but
change Boto3 use to support the normal credential provider chain. That enables
an EC2 role when hosted on AWS, and a later IAM Roles Anywhere adoption for a
Raspberry Pi or other non-AWS host. [AWS recommends temporary role
credentials](https://docs.aws.amazon.com/IAM/latest/UserGuide/securing_access-keys.html)
over long-lived access keys where possible.

### P1: Deployment verification and governance are incomplete

The production AWS workflow correctly deploys only by manual dispatch from
`main`, but it has no post-deploy verification, no drift check, and no
production GitHub Environment. It also does not provide pull-request or push
validation for infrastructure changes; the full validation suite runs only in
the manual production deployment workflow.

Add a no-secret infrastructure CI workflow for pull requests and pushes that
runs formatting, linting, typing, unit tests, Lambda lock checks, and fixture
synthesis. Then add a protected `production` GitHub Environment to the deploy
job, with an approval rule if appropriate, and narrow post-deployment read
permissions to stack outputs and Lambda configuration.

Adding a GitHub Environment changes the default OIDC subject from a branch
subject to an environment subject. Verify an actual OIDC claim and update the
manual trust policy before making that change. GitHub also documents immutable
OIDC subject formats for newly created or renamed repositories. See [GitHub
OIDC claims](https://docs.github.com/en/actions/reference/security/oidc) and
[deployment environments](https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments).

### P2: Lambda source duplication is high

The AI-note and AI-summary handlers independently implement configuration,
S3 transcript retrieval/retries, internal API calls, OpenRouter calls, models,
and batch handling. Keep each Lambda as an independently deployable ZIP, but
eliminate source-level duplication with a shared worker package:

```text
backend/workers/
  lambda_runtime/src/vidwiz_worker/
    config.py
    errors.py
    transcript_store.py
    internal_api.py
    openrouter.py
    message_models.py
  lambdas/
    transcript_dispatcher/handler.py
    ai_note_worker/handler.py
    ai_summary_worker/handler.py
```

Each handler should only parse the event, call a domain service, and return or
raise. Bundle the shared package into each function artifact first; do not add
a Lambda layer unless package size or build time proves it useful. A layer
would add version coupling without reducing the need to deploy every consumer
when shared source changes.

Create one versioned message schema for the backend producer and Lambda
consumer, and keep a producer/consumer contract test in the backend suite.

### P2: Production Docker delivery is not represented in the repository

The repository no longer contains the former Docker image build/deploy
workflows. That removes the conflicting Compose/systemd behavior, but leaves
the actual production Docker delivery process outside version control.

Choose and document one deployment owner before rebuilding automation. The
minimum safe contract should deploy an immutable image digest or commit tag,
project component-specific environment variables, run health checks, retain a
rollback target, and avoid stopping PostgreSQL for an API-only release. Docker
recommends production-specific Compose overlays and targeted recreation rather
than full stack teardown. See [Use Compose in
production](https://docs.docker.com/compose/how-tos/production/).

### P2: Infrastructure is production-only

`vidwiz-stack`, its physical names, tags, account region, and manual policies
are production-specific. The application supports `local` and `staging`
runtime modes, but there is no corresponding isolated AWS environment.

Do not clone the current stack. First make an environment identity explicit:

```text
EnvironmentConfig
  name                 # staging or production
  account and region
  stack and resource prefix
  data retention policy
  worker sizing and tuning
  secret/parameter paths
```

Prefer separate AWS accounts for staging and production. If that is not yet
practical, use isolated stack names, bucket names, queues, roles, secrets, and
resource prefixes in the same account. Keep production retention behavior
separate from disposable non-production resources.

## Recommended Delivery Sequence

1. **Reliability first:** fix S3/SQS retry semantics, add DLQs, and add
   durable idempotency before refactoring shared code.
2. **Extract the worker runtime:** introduce shared source modules, thin
   handlers, typed settings, reusable clients, and versioned message schemas.
3. **Separate configuration from secrets:** project least-privilege Compose
   variables, move Lambda secrets to AWS, and support the standard AWS
   credential provider chain.
4. **Add environments and CI:** create no-secret infrastructure CI, then
   staging and protected production deployment environments.
5. **Restore reproducible Docker delivery:** decide the deployment owner,
   deploy immutable images, verify health, and support rollback.

## Production Readiness Checklist

Before relying on the workflow for a production cutover, verify:

- The manual OIDC trust policy matches the actual GitHub token subject.
- The reviewed Lambda source is bundled by CDK and every lockfile is current.
- Every transient S3, SQS, API, and provider failure is retried rather than
  acknowledged.
- Queue redrive, DLQ alerting, and replay procedures are tested.
- S3 multi-record delivery and duplicate delivery are covered by regression
  tests.
- AI note and summary work have durable idempotency/claim state.
- The retained bucket recovery and transcript-copy runbook have been rehearsed
  with event processing disabled or safely replayed after cutover.
- Production configuration and secrets have a defined owner, rotation process,
  and least-privilege consumer mapping.
- The deployment has a post-deploy smoke check and a documented rollback path.

## References

- [AWS Lambda with SQS](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html)
- [AWS Lambda SQS error handling](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-errorhandling.html)
- [AWS Lambda asynchronous error handling](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-error-handling.html)
- [Amazon S3 event message structure](https://docs.aws.amazon.com/AmazonS3/latest/userguide/notification-content-structure.html)
- [AWS Secrets Manager with Lambda](https://docs.aws.amazon.com/lambda/latest/dg/with-secrets-manager.html)
- [GitHub OIDC claims](https://docs.github.com/en/actions/reference/security/oidc)
- [GitHub deployment environments](https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments)
- [Docker Compose in production](https://docs.docker.com/compose/how-tos/production/)
