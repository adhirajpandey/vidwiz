# Reconcile the final v3 data

Keep the existing v3 database. Import only the approved missing production
notes, their videos, library membership, and AI charges. Do not restore a new
production dump over v3.

This is a one-time operation, not a sync service. The command stops on
unreviewed notes, account identities, tokens, conversations, messages, payment
changes, ledger conflicts, or active processing. It never calls application
services, S3, AI, payment, email, or queue APIs.

## Policy and limits

- Keep all existing v3 rows, including test accounts, empty conversations,
  pending checkouts, revoked tokens, and historical ledger entries.
- Keep v3 passwords, settings, balances, video metadata, overviews, and activity
  timestamps. Existing transcript chunks and citation IDs remain unchanged.
- Match accounts by ID plus email, Google ID, and creation time. A production
  long-term token must match an existing v3 hash; a revoked match stays revoked.
  New accounts, rotated production tokens, or an active v3 legacy token removed
  in production require review.
- Identify existing migrated moments by legacy source and ID, and verify their
  owner, video, capture time, text, and activity times. Changed legacy moments
  stop the operation. Missing legacy moments require an explicit import or
  exclusion decision, bound to that source row's SHA-256 fingerprint.
- New imported moments, videos, chunks, and ledger entries get IDs above both
  surviving rows and the current sequence values, avoiding reuse after deletions.
  The receipt records the source-to-destination mappings. Nearby moments are
  not merged. Library entries use the earliest imported capture time when no
  membership exists; existing membership stays unchanged.
- Normalize legacy AI-note charges to AI-moment references and deduplicate by
  owner, reason, reference type, and mapped reference ID. Conflicting amounts
  or times stop the operation. Add an explicit offsetting adjustment for new
  imported charges, preserving both v3 balances and pre-existing differences
  between balances and ledger totals. Do not reconstruct balances from totals.
- New production purchases, chats, or unrelated ledger entries are outside
  this reviewed import. Stop and extend the reviewed policy if these appear.
- Preserve existing v3 jobs. Do not import or replay production jobs. Both
  databases must have no active or retryable tasks. Queued v3 AI/overview jobs
  and resolving captures also block the import. Existing unresolved or
  waiting-for-transcript captures remain intact; verify their external jobs
  are paused before proceeding.
- Read transcript JSON from local files. Build chunks only for new videos and
  quotes only for imported moments. Preserve old generated content. Do not
  run an overview backfill or infer an AI model for historical output.

## Prepare the inputs

Use a private directory outside the repository with mode `0700`. Export files,
policies, plans, transcript files, and results contain private data. The command
creates output files with mode `0600` and refuses to overwrite them. Keep them
with the database backups; never commit them.

Use the existing backend environment (`uv sync --locked` when needed). The
command itself does not require application settings or cloud credentials.
Pass database connection strings privately through `RECONCILE_SOURCE_DSN` and
`RECONCILE_TARGET_DSN`, not command-line arguments. Neither has a default.

The source must have the legacy production schema. The target must have v3
migration `0008`, which adds only `reconciliation_receipt`. Run the normal
Alembic migration process separately, after backing up and authorizing any live
schema change. This command does not run schema migrations.

From `backend/`, export a consistent, read-only source snapshot:

```sh
python -m src.management.reconcile export --out /private/source.json
```

Create `/private/policy.json` with exactly these keys:

```json
{
  "keep_v3_accounts_and_balances": true,
  "exclude_notes": {},
  "import_notes": {}
}
```

For each reviewed note, put its string ID and fingerprint in the appropriate
map. Compute the fingerprint with `digest(row)` from
`src.management.reconcile`, using the exact row in `source.json`. Do not approve
all missing rows automatically. An exclusion is valid only while its destination
ID is absent and the source row still matches the reviewed fingerprint.
Changed or additional source notes require a new decision.

Create `/private/transcripts.json` as an object keyed by video ID, with each
value being the existing transcript segment array. Use `{}` if no transcripts
are needed. Include transcripts for every imported moment on a transcript-ready
video. For an existing v3 video, use its v3 transcript. For a new video, use the
production transcript. Ready videos require a nonempty local transcript; the
command does not fetch missing files or generate content.

Read the relevant S3 objects separately. Record their content hashes in the
private cutover notes. The plan binds the local transcript contents by hash;
it cannot verify the bucket or pause its event triggers.

## Review the plan

```sh
python -m src.management.reconcile plan \
  --source /private/source.json --policy /private/policy.json \
  --transcripts /private/transcripts.json --out /private/plan.json
```

Review `counts`, `maps`, `excluded_notes`, `balance_adjustments`, and `inserts`.
The plan includes exact imported rows and hashes of the source, policy, local
transcripts, and entire target data snapshot, including sequence values. Existing target rows do not appear
in the output, but their counts appear in `preserved`.

Planning is read-only. It stops at the first conflict and names the affected
record without printing its content. SQL and connection errors are redacted.

There is no live-copy rehearsal in this workflow. Focused tests use synthetic
records in a disposable PostgreSQL database:

```sh
TEST_DB_URL='<disposable PostgreSQL URL>' python -m pytest -q \
  src/tests/test_reconcile.py src/tests/test_transcripts.py
```

The repository's test fixture resets the database named by `TEST_DB_URL`.
Never use either deployment database for tests.

## Apply during the authorized maintenance window

1. Pause writes in both apps, including payment callbacks and token usage.
   Pause helpers, sweepers, S3 dispatch triggers, and queue consumers. Let
   in-flight work settle and inspect pending deliveries. A database lock alone
   does not stop external systems.
2. Back up both databases, roles needed for restore, and relevant transcript
   objects. Keep the exact application revision and deployment settings with
   the recovery notes. Apply migration `0008` to the target if still needed.
3. Export the frozen source again. Recheck decisions against the fresh rows.
   Prepare and review a fresh plan against the frozen target.
4. Copy only missing transcript objects to the destination bucket while upload
   triggers remain paused. Verify bytes match the files used for planning.
   Never overwrite an existing different object without review. Record newly
   copied keys for recovery. This step is separate from the database transaction.
5. Apply the exact reviewed plan:

   ```sh
   python -m src.management.reconcile apply \
     --source /private/source.json --policy /private/policy.json \
     --transcripts /private/transcripts.json --plan /private/plan.json \
     --out /private/result.json
   ```

   The command locks target tables, recomputes the plan, and rejects changed
   inputs or target data. It inserts rows and the receipt in one transaction,
   verifies old rows are unchanged, checks counts and ledger offsets, then
   advances sequences without lowering them. Table locks time out after five
   seconds rather than waiting indefinitely.
6. Inspect the result and receipt. Run the same apply command with a new output
   filename. It must return `already_applied: true` without writing data.
   This checks the original receipt, not subsequent application data. A receipt
   from different inputs or a different plan blocks further imports.
7. Verify imported records and transcript availability before enabling writes.
   Keep the 178 deferred overviews deferred; do not run broad backfills.
   Coordinate the API/frontend switch and production configuration separately.
   Resume only reviewed jobs, with valid IDs and callbacks for the final stack.

## Failure and recovery

Before commit, a failure rolls back inserts and the receipt. PostgreSQL sequence
advances are not transactional, so failure can leave harmless gaps. If sequence values changed, regenerate
and review the plan before retrying. Otherwise rerun with unchanged inputs after
resolving the cause. A stale plan must be regenerated
and reviewed; never edit it to bypass the checks.

If commit succeeds but writing the result file fails or the connection drops,
retry the original command with a fresh output path. The persisted receipt
prevents a second import. Do not delete or downgrade the receipt table to force
another run. Keep all original input and plan files.

Before reopening writes, restore the pre-operation v3 backup if the migration
must be abandoned. Keep the old public deployment in place. Restore database and
transcript state together; separately copied objects are not rolled back by SQL.
Remove only objects recorded as newly copied, and only when authorized.

After writes resume, take another backup and preserve new activity before any
rollback. Restoring the older backup directly would lose those writes. The
receipt is an audit record, not an automatic reverse migration. Do not delete
the old stack or its backups as part of reconciliation.
