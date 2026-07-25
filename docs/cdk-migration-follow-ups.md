# CDK Migration Follow-up Plan

## Purpose

This document consolidates the corrections and maintainability improvements
identified during review of the `feat/cdk-migration` branch. It is an
implementation plan, not an authorization to deploy, migrate transcripts, or
remove legacy AWS resources.

The goals are to make the production deployment path reliable, ensure the
reviewed Lambda source is what gets deployed, and replace implicit naming and
configuration conventions with explicit contracts.

The recommendations below were validated against the migration branch,
surrounding application code, and primary GitHub, AWS, CDK, Python, Pydantic,
and uv documentation. Items labelled as operational choices still require
production-specific decisions; they are not universal implementation defaults.

### Implementation status

The custom Lambda ZIP packaging recommendation in section 2 has been
superseded by CDK-managed `PythonFunction` bundling. Lambda source directories
now contain `handler.py`, `pyproject.toml`, and `uv.lock`; CDK creates and publishes the
assets during synthesis and deployment. References below to custom packaging,
build images, and artifact manifests are retained only as the original review
rationale and do not describe the current implementation.

## Priority Order

Complete the first group before relying on the CDK workflow for production.

1. Fix deployment authentication and post-deploy verification permissions.
2. Fix Lambda artifact provenance and explicit Lambda-to-package mapping.
3. Fix S3/SQS failure semantics so transient failures are retried rather than
   acknowledged and lost.
4. Process every record delivered in an S3 event.
5. Correct the initial-deployment and transcript-migration runbooks.
6. Make the single GitHub configuration file unambiguous, immune to ambient
   overrides, and validate its deployment target.
7. Complete the structural cleanup and CI contract coverage.

## 1. Deployment Authentication and Verification

### Align GitHub OIDC trust with the deployment triggers

The deployment job does not declare a GitHub Environment, so GitHub's default
OIDC subject remains the `main` branch reference accepted by the manually
created role policy. Relevant pushes to `main` deploy automatically, and
manual dispatch remains available only from `main`. The job guard enforces
both trigger and ref:

```yaml
if: >-
  github.ref == 'refs/heads/main' &&
  (github.event_name == 'push' || github.event_name == 'workflow_dispatch')
```

Before applying the policy, inspect an actual GitHub OIDC token claim. Custom
subject templates can change the exact value, so the trust policy must match
the repository's configured format.

### Permit post-deployment verification

The GitHub deployment role is intentionally limited to assuming CDK bootstrap
roles. That is enough for `cdk deploy`, but the later standalone AWS CLI calls
run as the original GitHub role, not as the temporary CDK deploy-role session.

Choose one of these approaches:

- Grant the GitHub role narrowly scoped `cloudformation:DescribeStacks` for
  `vidwiz-stack` and `lambda:GetFunctionConfiguration` for the three Lambda
  functions.
- Explicitly assume an appropriate read-capable role before verification and
  export the resulting temporary credentials for that step.

## 2. Lambda Packaging and Deployment Provenance

### Make Lambda definitions explicit

One Lambda currently has several independently maintained identities:

| Concern | Current transcript dispatcher name |
|---|---|
| Source file | `tasks-dispatcher.py` |
| Package key and ZIP stem | `transcript-dispatcher` |
| CDK construct | `TranscriptDispatcher` |
| Physical Lambda name | `vidwiz-prod-transcript-dispatcher` |
| Packaged handler module | `lambda_function.py` |

The stack chooses the package with a substring search against the physical
function name. This makes a rename brittle and can select the wrong package if
names later overlap.

The implementation replaces `PACKAGES` plus the `_function()` substring lookup
with a single explicit definition registry shared by packaging and CDK:

```python
@dataclass(frozen=True)
class LambdaSpec:
    key: str
    artifact_stem: str
    construct_id: str
    function_name: str
    source: Path
    requirements: Path
    required_imports: tuple[str, ...]
    handler: str
```

`packaging.py` builds each `LambdaSpec`; `stack.py` receives that same spec
directly. Tests assert every spec maps to exactly one source, artifact,
function name, and handler.

### Use meaningful Python module names

The former hyphenated source names could not be imported as Python modules and
forced the build to rename every source to `lambda_function.py`. Each Lambda
now has one source directory:

```text
backend/workers/lambdas/
  transcript_dispatcher/handler.py
  ai_note_worker/handler.py
  ai_summary_worker/handler.py
```

Each directory's contents are copied into its independent ZIP root without
renaming, so every deployed artifact contains root-level `handler.py` and uses
`handler.lambda_handler`. The artifact and explicit specification provide the
Lambda identity without adding a nested package solely for deployment.

### Prove that the ZIP matches the reviewed source

`stack.py` currently only checks whether the ZIP exists, while its custom CDK
asset hash is recomputed from the current source. A stale ZIP can therefore be
uploaded with a hash that describes newer source code.

Prefer CDK bundling so the asset is built as part of synthesis. If separate
packaging remains necessary, create a manifest next to each ZIP containing:

- source hash;
- requirements hash;
- packaging-code hash;
- exact build-image reference; and
- artifact hash.

Require `stack.py` to validate the manifest before accepting the artifact.

### Use one build-image identity

The code hashes `BUILD_IMAGE_ID` but Docker executes `BUILD_IMAGE`. The two
references may intentionally be a manifest list and its AMD64 child image, but
the code does not prove that relationship.

Prefer one immutable `LAMBDA_BUILD_IMAGE` reference for both Docker execution
and the artifact hash. If a manifest and platform-specific digest are both
required, name them explicitly and verify their relationship in a test.

### Support documented local validation

`os.getuid()` and `os.getgid()` are Unix-only. If native Windows local
validation is supported, make Docker's `--user` argument conditional. Also make
the documented lock-regeneration tool reproducible: either pin `pip-tools`, or
replace the documented command with a reviewed `uv pip compile` or pinned `uvx`
workflow and verify the resulting lockfiles.

## 3. Event and Queue Failure Semantics

### Preserve retry behavior for SQS workers

The AI note and summary handlers currently catch operational failures and return
normally. The new SQS event mappings treat that as a successful invocation, so
Lambda deletes the message on the first attempt.

With the current batch size of one, make retriable provider and infrastructure
failures raise from the handler. Keep malformed messages and permanent business
rejections distinct so they do not retry forever. Alternatively, implement
Lambda partial-batch responses and set `report_batch_item_failures=True`.

Add dead-letter queues and redrive policies for terminal failures. AWS strongly
recommends a redrive policy; choose max receives, retention, alerting, and a
replay procedure as production operational decisions.

### Preserve retry behavior for the S3 dispatcher

The dispatcher also catches API and SQS failures. An S3-triggered Lambda
invocation then succeeds from Lambda's perspective, so asynchronous retry does
not occur.

Make failed note lookup, summary enqueue, and note enqueue operations fail the
invocation after recording context. Add idempotency before relying on retries,
because S3 and SQS delivery are at least once.

### Process every S3 event record

The dispatcher currently reads only `Records[0]`. An S3 notification can carry
multiple records, so later transcript objects in the same invocation are
silently skipped. Iterate every S3 record, URL-decode each object key before
extracting the video ID, and add a regression test with multiple records.

### Name runtime contracts by their domain

Use `SQS_AI_NOTE_QUEUE_URL` and `SQS_AI_SUMMARY_QUEUE_URL` for queue URLs,
`S3_TRANSCRIPT_BUCKET_NAME` for transcript storage, and
`VIDWIZ_INTERNAL_API_BASE_URL` plus `VIDWIZ_INTERNAL_API_ADMIN_TOKEN` for
worker access to the internal API.

Treat the backend note payload and Lambda note model as one contract. Add a
shared schema or contract test covering the producer in
`backend/src/notes/service.py` and the worker consumer.

## 4. Storage Lifecycle and Migration Runbook

### Make first-deployment recovery possible

The transcript bucket has a fixed global name and `RemovalPolicy.RETAIN`.
During an initial stack-create rollback, CloudFormation can retain that bucket
outside the failed stack. The next deployment cannot recreate or automatically
adopt it under the same name.

Use retain-except-on-create semantics (`RETAIN_ON_UPDATE_OR_DELETE`) for this
resource, or explicitly document the import/recovery procedure for an orphaned
bucket. Keep the normal deletion and replacement retention behavior for
accepted production data.

### Retain the bucket policy with the bucket

The generated bucket policy that enforces HTTPS is a separate CloudFormation
resource. Retaining the bucket without retaining the policy leaves data behind
but removes that security control if the stack is deleted.

Apply matching retention behavior to the bucket policy, or document and
automate the policy restoration procedure.

### Correct transcript-copy sequencing

Copying transcript objects triggers the dispatcher, which requires the backend
internal API. The current runbook suggests stopping the Docker application
during copying, which makes dispatch fail. It also describes duplicate work as
idempotent even though duplicate deliveries can repeat AI-note generation and
its external model cost.

Choose one safe sequence:

1. If the legacy and new paths can safely coexist, keep the backend available
   during copying, make workers idempotent, and verify all dispatch results
   before cutover; or
2. Disable the new event processing during copying, complete the application
   cutover, then explicitly replay the copied transcript keys.

Do not describe the process as idempotent until note generation has a durable
idempotency mechanism.

## 5. One GitHub-managed Configuration File

One multiline GitHub secret is a valid source of all production configuration.
The problem is not having one file; it is calling that mixed deployment input a
Lambda environment file.

Rename the GitHub secret and path variable:

```text
PRODUCTION_DEPLOYMENT_ENV
VIDWIZ_PRODUCTION_CONFIG_PATH
```

The temporary file should have a corresponding name such as
`vidwiz-production-config.XXXXXX`.

Keep one file, but split it into explicit in-memory models after parsing:

```text
ProductionDeploymentConfig
  DeploymentTarget       # account and region
  WorkerSizing           # memory and timeout by worker
  RuntimeConfiguration   # URLs, model, retry and length settings
  RuntimeSecrets         # internal API admin token and OpenRouter key
```

The non-secret values are used during CDK synthesis. The secret values are
extracted from the same file only at deploy time and supplied as CloudFormation
parameter values, which then become Lambda environment variables.

### Load the explicit file without ambient overrides

`ProductionSettings.from_env_file()` currently still reads process environment
variables first because Pydantic gives them higher precedence than dotenv
values. A runner or developer variable can therefore silently override the
reviewed GitHub secret file.

For this explicit-file loader, customize Pydantic settings sources to omit
`env_settings` (or parse the file and pass only its values). Add a regression
test that sets a conflicting process variable and proves the file remains the
source of truth.

Use terminology that distinguishes the layers:

| Current term | Recommended term |
|---|---|
| `LAMBDA_ENV_FILE` | `PRODUCTION_DEPLOYMENT_ENV` |
| `LAMBDA_ENV_FILE_PATH` | `VIDWIZ_PRODUCTION_CONFIG_PATH` |
| `ProductionSettings` | `ProductionDeploymentConfig` |
| `VIDWIZ_TOKEN_PARAMETER` | `CFN_VIDWIZ_INTERNAL_API_ADMIN_TOKEN_VALUE` |
| `OPENROUTER_API_KEY_PARAMETER` | `CFN_OPENROUTER_API_KEY_VALUE` |
| `export_secret_parameters.py` | `prepare_deploy_parameters.py` |
| `VIDWIZ_ENDPOINT` | `VIDWIZ_INTERNAL_API_BASE_URL` |
| `VIDWIZ_TOKEN` | `VIDWIZ_INTERNAL_API_ADMIN_TOKEN` |

Use consistent `OpenRouter` casing in CloudFormation parameter names as well.

### Declare one source of truth for the deployment target

The AWS account currently appears in both the GitHub variable and the secret
configuration file, while the region is also hard-coded in the workflow.

Choose a primary target configuration and compare every other source against it
before synthesis. The workflow must fail early if the GitHub caller account,
configured CDK target account, or region differs.

## 6. Workflow and CI Boundaries

### Deploy the synthesized assembly, not a second synthesis

The workflow runs `cdk synth` and then `cdk deploy`, which synthesizes again.
The first assembly is discarded, so it is not the exact artifact deployed.

Either keep the first command as an explicitly named preflight, or synthesize
once and deploy the generated cloud assembly (for example with `--app cdk.out`)
after review and validation.

### Enforce lockfile freshness

Use `uv sync --locked` and `uv run --locked` so every command verifies that
`uv.lock` matches `pyproject.toml` and cannot update the lock during CI or CDK
synthesis. This now matches the intent already expressed by `npm ci`.

### Check whitespace in the actual change range

`git diff --check` without commits compares the checkout worktree to its index,
which normally contains no PR changes. It does not validate the pull request
diff.

For pull requests, use the explicit range:

```text
git diff --check ${{ github.event.pull_request.base.sha }}...${{ github.sha }}
```

Choose and document a deliberate comparison range for manually dispatched
runs.

### Trigger validation for both sides of the queue contract

The infrastructure workflow watches `infra/**` and Lambda source paths, but it
does not watch the backend code that creates AI-note messages or defines
`SQS_AI_NOTE_QUEUE_URL`. Include the producer and relevant backend configuration
paths in the trigger, and run the producer/consumer contract test there.

### Automatic-deployment transition

The workflow deploys relevant pushes to `main` and retains manual dispatch from
`main`. Both paths share the branch-scoped OIDC trust; pull requests run only
validation and receive neither OIDC credentials nor production secrets.

## 7. Resource Names, Manual Policies, and Documentation

Move bucket, queue, and function physical names to a neutral module such as
`infra/vidwiz_infra/resource_names.py`. Use it from the CDK stack and manual
policy generator. Prefer CloudFormation stack outputs for post-deployment
verification instead of repeating function names in the workflow.

The manual policy module is useful, but the runbook should provide an explicit
command that renders the returned dictionaries as policy JSON. For example:

```text
uv run --locked python scripts/render_manual_policy.py github-deploy-role
uv run --locked python scripts/render_manual_policy.py application-user
```

Document that these policies are bootstrap resources outside the CDK stack and
that changing a physical resource name requires regenerating them.

## Validation Checklist

Before the first production deployment, verify all of the following:

- OIDC trust accepts the `main` branch subject and both deployment paths are
  restricted to `main`.
- The GitHub deployment role can complete post-deploy reads, or the workflow
  explicitly assumes a read-capable role.
- Each Lambda spec has an exact source-directory-to-function mapping, and CDK
  bundles the reviewed source during synthesis.
- SQS and S3 transient failures are retried, with DLQs for terminal failures.
- The dispatcher processes every `Records` item in an S3 event and has a
  multi-record regression test.
- The transcript-copy procedure keeps required internal API dependencies
  available or replays events after cutover.
- A failed initial stack creation can be recovered without an orphaned bucket
  blocking redeployment.
- The retained bucket retains or restores its HTTPS enforcement policy.
- The single production configuration file passes validation and agrees with
  the GitHub deployment target.
- The explicit production-file loader cannot be overridden by ambient process
  environment variables.
- CI validates Lambda code, the backend queue producer, and their shared
  message contract.
- The final deployment uses the reviewed synthesized cloud assembly.
- CI whitespace validation compares the intended commit range rather than a
  clean checkout worktree.

## Primary References Used for Validation

- [GitHub OIDC claims](https://docs.github.com/en/actions/reference/security/oidc)
  and [OIDC with AWS](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)
- [AWS CDK deployment](https://docs.aws.amazon.com/cdk/v2/guide/deploy.html)
  and [CDK removal policies](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk/RemovalPolicy.html)
- [CloudFormation deletion policies](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-attribute-deletionpolicy.html)
  and [S3 bucket policies](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-s3-bucketpolicy.html)
- [Lambda with SQS](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html),
  [SQS error handling](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-errorhandling.html),
  and [asynchronous Lambda failure handling](https://docs.aws.amazon.com/lambda/latest/dg/invocation-async-error-handling.html)
- [Amazon S3 event notifications](https://docs.aws.amazon.com/AmazonS3/latest/userguide/EventNotifications.html)
  and [AWS Powertools S3 event data classes](https://docs.aws.amazon.com/powertools/python/latest/utilities/data_classes/#s3)
- [Pydantic settings source priority](https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/#field-value-priority)
- [uv project sync and locking](https://docs.astral.sh/uv/concepts/projects/sync/)
  and [git diff](https://git-scm.com/docs/git-diff.html)
