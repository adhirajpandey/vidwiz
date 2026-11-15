# Workflow health and batch budgets

Current workflow metrics count items by stage. Historical task attempts remain
in the database and event counters retain their attempt semantics.

- Metadata uses the newest attempt per video, ordered by creation time and ID.
  Existing metadata or a successful latest attempt suppresses older failures.
- Transcript-ready videos suppress old fetch failures. Confirmed missing
  transcripts and private/deleted videos are `unavailable`. Failed attempts
  with transient or uncertain causes are `failed`. Legacy unavailable videos
  without a retained terminal attempt are `unknown`.
- Helpers persist bounded `error_kind` values. Historical messages are classified
  only when they contain a narrow, recognizable cause. Blocking, proxy, and
  timeout evidence takes precedence over unavailable wording.
- Nonempty title candidates are `awaiting_user`; empty candidates are not a
  choice. Explicit no-result searches are `not_found`. Choices never expire.
- AI notes without a resolved video are `waiting_title`. Notes and overviews
  stopped by transcript availability are `blocked`; inspect the transcript's
  state to understand why. These are separate from processing failures.
- Current counts are per stage, not globally unique users or videos. One video
  can have both metadata and transcript failures. Snapshot freshness still gates
  all counts. Event increases are approximate and can lose events between
  scrapes during restarts.

## Capture timestamps

New captures and saved passages reject times beyond a known, finite, positive
video duration before saving or charging. Exactly the video duration is allowed.
Unknown duration does not block capture.

If metadata arrives later, outstanding AI work becomes `invalid_timestamp`.
The note and original timestamp remain intact. The UI asks the user to capture
again at the correct time. Pending-job collection and worker callbacks also
check the duration; the worker checks before calling the model when metadata is
available. An already-running model request cannot be cancelled by this check.
Completed AI notes are preserved. There is no automatic timestamp clamp.

Migration `0011` adds the allowed state. Apply it before deploying the API,
then deploy the helper and AI note worker changes. Deploy the frontend with the
new status copy. On rollback, stop new writes first; the migration downgrade
maps `invalid_timestamp` to `failed` before restoring the old constraint.
Existing failed rows are classified by the monitoring query without rewriting
history. They acquire the new persisted state when metadata or AI work is handled.

## Overview backfills

The command now plans by default and requires an explicit estimate and reserve:

```sh
python -m src.management.backfill overviews --limit 10 \
  --estimate-usd-per-overview 0.01 --reserve-usd 1
```

Use a measured estimate for the actual model and input sizes. The numbers above
are examples, not model prices. Add `--apply` to queue the planned batch. A fresh
provider check must establish enough available budget for the estimated cost
plus the reserve. Unknown budget, invalid estimates, and insufficient headroom
stop the command before it queues jobs. Other effective provider budgets also
constrain admission when returned by the provider.

This is an admission estimate, not a reservation or spending cap. Other activity,
retries, and variable output lengths can consume more than estimated. The
provider's configured limit remains the hard enforcement mechanism. This change
does not raise that limit or run any backfill.

## Budget and interruption evidence

The budget poller publishes `vidwiz_llm_budget_reset_timestamp_seconds` along
with remaining amount, limit, and the last successful check timestamp. Malformed
responses leave the previous values and timestamp unchanged. Unknown or
non-resetting periods produce `NaN`. Daily, weekly, and monthly reset times use
OpenRouter's documented UTC boundaries: midnight, Monday midnight, and the first
of the month. See the [provider limits reference](https://openrouter.ai/docs/api-reference/limits).

Dashboard and agent budget values should be treated as stale after ten minutes.
The displayed key cap does not establish account credit or all workspace limits.

The API emits `service.started` and `service.stopping` lifecycle logs with a
sanitized build revision. Release images receive `APP_REVISION` from CI. A local
or older build reports `unknown`. A startup marker alone does not establish that
a deployment happened; compare revisions. Abrupt termination may have no stop
marker. Database startup/shutdown logs provide separate restart evidence.

Alerts remain disabled. Establish thresholds after validating the new item
classification against live data; a historical failure is not a new incident.
