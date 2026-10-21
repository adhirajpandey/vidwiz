"""Bounded final v2 -> v3 reconciliation. No application services or network APIs.

See docs/reconciliation.md. All file artifacts contain private data.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json

from src.transcripts import chunk_transcript, quote_for

SOURCE_TABLES = (
    "users",
    "videos",
    "notes",
    "conversations",
    "messages",
    "credits_ledger",
    "credit_purchases",
    "tasks",
)
TARGET_TABLES = (
    "users",
    "videos",
    "moments",
    "conversations",
    "messages",
    "credits_ledger",
    "credit_purchases",
    "tasks",
    "library_items",
    "api_tokens",
    "transcript_chunks",
)
INSERT_TABLES = (
    "videos",
    "moments",
    "library_items",
    "transcript_chunks",
    "credits_ledger",
)


class Conflict(ValueError):
    """Inputs require a new decision. Never print record contents or credentials."""


def require(condition, message):
    if not condition:
        raise Conflict(message)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def rows_by_id(rows):
    result = {r["id"]: r for r in rows}
    require(len(result) == len(rows), "Duplicate source IDs")
    return result


def normalized(data):
    return {
        t: sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))
        for t, rows in data.items()
    }


def snapshot(conn, tables):
    result = {}
    with conn.cursor() as cur:
        cur.execute("SET LOCAL TIME ZONE 'UTC'")
        for table in tables:
            cur.execute(
                sql.SQL("SELECT to_jsonb(t) - 'search' FROM {} t").format(
                    sql.Identifier(table)
                )
            )
            result[table] = [r[0] for r in cur.fetchall()]
        if tuple(tables) == TARGET_TABLES:
            result["_sequences"] = []
            for table in INSERT_TABLES:
                if table == "library_items":
                    continue
                cur.execute("SELECT pg_get_serial_sequence(%s, 'id')", (table,))
                sequence = cur.fetchone()[0]
                require(sequence is not None, f"Missing sequence: {table}")
                cur.execute(
                    sql.SQL("SELECT last_value, is_called FROM {}").format(
                        sql.Identifier(*sequence.split("."))
                    )
                )
                value, called = cur.fetchone()
                result["_sequences"].append(
                    dict(table=table, last_value=value, is_called=called)
                )
    return normalized(result)


def input_hash(source, policy, transcripts):
    return digest(
        {"source": normalized(source), "policy": policy, "transcripts": transcripts}
    )


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.replace(tzinfo=None)


def legacy_note(row):
    parts = row["timestamp"].split(":")
    seconds = (
        0
        if row["timestamp"].startswith("-")
        else sum(int(p) * 60**i for i, p in enumerate(reversed(parts)))
    )
    return {
        "user_id": row["user_id"],
        "video_id": row["video_id"],
        "at_seconds": seconds,
        "ai_text": row["text"] if row["generated_by_ai"] is True else None,
        "note": row["text"] if row["generated_by_ai"] is False else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def same_fields(left, right, fields):
    for field in fields:
        a, b = left.get(field), right.get(field)
        if field.endswith("_at") and a is not None and b is not None:
            a, b = timestamp(a), timestamp(b)
        if a != b:
            return False
    return True


def ledger_key(row):
    return tuple(row[k] for k in ("user_id", "reason", "ref_type", "ref_id"))


def normalize_charge(row):
    row = dict(row)
    if row["reason"] == "ai_note" and row["ref_type"] == "note":
        row.update(reason="ai_moment", ref_type="moment")
    return row


def verify_scope(source, target, policy):
    require(set(source) == set(SOURCE_TABLES), "Unexpected source tables")
    require(
        set(target) == set(TARGET_TABLES) | {"_sequences"}, "Unexpected target tables"
    )
    require(
        set(policy)
        == {"keep_v3_accounts_and_balances", "exclude_notes", "import_notes"},
        "Unexpected policy keys",
    )
    require(
        policy["keep_v3_accounts_and_balances"] is True,
        "Explicit v3 account/balance policy required",
    )
    users = rows_by_id(target["users"])
    for user in source["users"]:
        other = users.get(user["id"])
        require(
            other and same_fields(user, other, ("email", "google_id", "created_at")),
            f"Account identity conflict: {user['id']}",
        )
        token = user.get("long_term_token")
        if token:
            h = hashlib.sha256(token.encode()).hexdigest()
            require(
                any(
                    t["user_id"] == user["id"] and t["token_hash"] == h
                    for t in target["api_tokens"]
                ),
                f"Legacy token changed or missing: user {user['id']}",
            )
        else:
            require(
                not any(
                    t["user_id"] == user["id"]
                    and t["name"] == "Legacy token"
                    and t["revoked_at"] is None
                    for t in target["api_tokens"]
                ),
                f"Legacy token removed in production: user {user['id']}",
            )
    # These tables have no production-only deltas in the reviewed scope.
    # A missing or changed row requires review, including deletions in either DB.
    for table in ("conversations", "messages", "credit_purchases"):
        old, new = rows_by_id(source[table]), rows_by_id(target[table])
        for key, row in old.items():
            require(
                key in new and same_fields(row, new[key], row.keys()),
                f"Unreviewed {table} change: {key}",
            )
            if table == "conversations":
                require(
                    new[key]["scope"] == "video", f"Conversation scope changed: {key}"
                )
        for key, row in new.items():
            if key not in old and source[table]:
                require(
                    row["created_at"]
                    and timestamp(row["created_at"])
                    > max(
                        timestamp(r["created_at"])
                        for r in source[table]
                        if r["created_at"]
                    ),
                    f"Possible production deletion: {table} {key}",
                )
    for name, data in (("source", source), ("target", target)):
        require(
            not any(
                t["status"] in ("PENDING", "IN_PROGRESS")
                or (t["status"] == "FAILED" and (t["retry_count"] or 0) < 3)
                for t in data["tasks"]
            ),
            f"Unsettled tasks in {name}",
        )
    require(
        not any(
            m["ai_status"] == "queued" or m["resolve_status"] == "resolving"
            for m in target["moments"]
        ),
        "Unsettled v3 moment processing",
    )
    require(
        not any(v["overview_status"] == "queued" for v in target["videos"]),
        "Unsettled v3 overviews",
    )


def build_plan(source, target, policy, transcripts):
    """Pure planner. Keep every target row; append only reviewed missing history."""
    verify_scope(source, target, policy)
    inserts = {t: [] for t in INSERT_TABLES}
    sequences = {s["table"]: s["last_value"] for s in target["_sequences"]}
    next_ids = {
        t: max(max((r["id"] for r in target[t]), default=0), sequences[t])
        for t in INSERT_TABLES
        if t != "library_items"
    }

    def allocate(table):
        next_ids[table] += 1
        return next_ids[table]

    require(
        isinstance(transcripts, dict)
        and all(
            isinstance(rows, list)
            and all(isinstance(r, dict) and "text" in r for r in rows)
            for rows in transcripts.values()
        ),
        "Invalid local transcript format",
    )
    notes = rows_by_id(source["notes"])
    moments = rows_by_id(target["moments"])
    exclusions = policy["exclude_notes"]
    for key, fingerprint in exclusions.items():
        require(
            int(key) in notes and digest(notes[int(key)]) == fingerprint,
            f"Exclusion changed: note {key}",
        )
        require(int(key) not in moments, f"Excluded note exists in v3: {key}")
    for moment in target["moments"]:
        if moment["source"] == "legacy":
            require(
                moment["id"] in notes,
                f"Possible production deletion: note {moment['id']}",
            )
    expected_new = {
        str(k)
        for k in notes
        if str(k) not in exclusions
        and (k not in moments or moments[k]["source"] != "legacy")
    }
    require(
        set(policy["import_notes"]) == expected_new,
        "Unreviewed missing notes; update explicit import/exclusion decisions",
    )
    for key, fingerprint in policy["import_notes"].items():
        require(
            digest(notes[int(key)]) == fingerprint,
            f"Approved import changed: note {key}",
        )
    maps = {"notes": {}, "videos": {}, "credits_ledger": {}}
    for key, row in sorted(notes.items()):
        if str(key) in exclusions:
            continue
        converted = legacy_note(row)
        other = moments.get(key)
        if other and other["source"] == "legacy":
            require(
                same_fields(converted, other, converted.keys()),
                f"Legacy note changed: {key}",
            )
            maps["notes"][str(key)] = key
        else:
            # A nonlegacy row is a collision, never a match or a nearby merge.
            converted.update(
                id=allocate("moments"),
                source="legacy",
                resolve_status="resolved",
                ai_status="ready" if row["generated_by_ai"] else "not_requested",
                quote=None,
                quote_start_seconds=None,
                ai_model=None,
                pending_title=None,
                pending_channel=None,
                resolve_candidates=None,
            )
            maps["notes"][str(key)] = converted["id"]
            inserts["moments"].append(converted)
    source_videos = {r["video_id"]: r for r in source["videos"]}
    target_videos = {r["video_id"]: r for r in target["videos"]}
    require(
        len(source_videos) == len(source["videos"]), "Duplicate source video identity"
    )
    needed = {r["video_id"] for r in inserts["moments"]}
    require(
        set(source_videos) - set(target_videos) <= needed,
        "Production-only video outside imported notes",
    )
    for vid in sorted(needed):
        require(vid in source_videos, "Missing source video")
        row = source_videos[vid]
        if vid in target_videos:
            maps["videos"][str(row["id"])] = target_videos[vid]["id"]
            continue
        has_transcript = bool(row["transcript_available"])
        require(
            not has_transcript or bool(transcripts.get(vid)),
            f"Local transcript required: {vid}",
        )
        video = {
            k: row[k]
            for k in (
                "video_id",
                "title",
                "video_metadata",
                "summary",
                "miscellaneous_data",
                "created_at",
                "updated_at",
            )
        }
        video.update(
            id=allocate("videos"),
            transcript_status="ready" if has_transcript else "unavailable",
            overview_status="ready"
            if row["summary"] is not None
            else ("pending" if has_transcript else "no_transcript"),
            overview_status_at=row["updated_at"] or row["created_at"],
        )
        require(
            video["overview_status_at"] is not None, f"Missing video timestamp: {vid}"
        )
        if video["title"] is None:
            title = (video["video_metadata"] or {}).get("title")
            if title and title.strip():
                video["title"] = title
        inserts["videos"].append(video)
        maps["videos"][str(row["id"])] = video["id"]
    library = {(r["user_id"], r["video_id"]) for r in target["library_items"]}
    for moment in sorted(inserts["moments"], key=lambda r: r["created_at"] or ""):
        vid = moment["video_id"]
        video = target_videos.get(vid)
        ready = (
            video["transcript_status"] == "ready"
            if video
            else bool(source_videos[vid]["transcript_available"])
        )
        require(
            not ready or bool(transcripts.get(vid)), f"Local transcript required: {vid}"
        )
        if ready:
            quote = quote_for(transcripts[vid], moment["at_seconds"])
            if quote:
                moment["quote"], moment["quote_start_seconds"] = quote
        key = (moment["user_id"], vid)
        if key not in library:
            require(
                moment["created_at"] is not None, "Missing library activity timestamp"
            )
            inserts["library_items"].append(
                dict(
                    user_id=key[0],
                    video_id=vid,
                    added_at=moment["created_at"],
                    last_opened_at=None,
                )
            )
            library.add(key)
    # Only new videos get chunks. Existing chunks (and citation IDs) stay intact.
    for video in inserts["videos"]:
        if video["transcript_status"] == "ready":
            for idx, (start, end, text) in enumerate(
                chunk_transcript(transcripts[video["video_id"]])
            ):
                inserts["transcript_chunks"].append(
                    dict(
                        id=allocate("transcript_chunks"),
                        video_id=video["video_id"],
                        idx=idx,
                        start_seconds=start,
                        end_seconds=end,
                        text=text,
                    )
                )
    ledger = {ledger_key(r): r for r in target["credits_ledger"]}
    require(
        len(ledger) == len(target["credits_ledger"]),
        "Duplicate target ledger reference",
    )
    totals = Counter()
    for original in sorted(source["credits_ledger"], key=lambda r: r["id"]):
        row = normalize_charge(original)
        if row["ref_type"] == "moment":
            row["ref_id"] = str(maps["notes"].get(row["ref_id"], row["ref_id"]))
        key = ledger_key(row)
        if key in ledger:
            require(
                same_fields(row, ledger[key], ("delta", "created_at")),
                f"Ledger conflict: {original['id']}",
            )
            maps["credits_ledger"][str(original["id"])] = ledger[key]["id"]
        else:
            # New purchases, grants, and orphan charges need a separate decision.
            require(
                row["reason"] == "ai_moment"
                and row["ref_type"] == "moment"
                and row["delta"] < 0
                and any(
                    str(m["id"]) == row["ref_id"] and m["user_id"] == row["user_id"]
                    for m in inserts["moments"]
                ),
                f"Unreviewed ledger entry: {original['id']}",
            )
            row["id"] = allocate("credits_ledger")
            inserts["credits_ledger"].append(row)
            maps["credits_ledger"][str(original["id"])] = row["id"]
            ledger[key] = row
            totals[row["user_id"]] += row["delta"]
    # No balance is recomputed from history: pre-existing offsets are preserved.
    for user_id, delta in sorted(totals.items()):
        if delta:
            inserts["credits_ledger"].append(
                dict(
                    id=allocate("credits_ledger"),
                    user_id=user_id,
                    delta=-delta,
                    reason="v3_reconciliation_adjustment",
                    ref_type="reconciliation",
                    ref_id="v3-final",
                    created_at=None,
                )
            )  # Set to transaction time at application, not historical activity.
    return {
        "format": 1,
        "input_hash": input_hash(source, policy, transcripts),
        "target_hash": digest(normalized(target)),
        "inserts": inserts,
        "maps": maps,
        "excluded_notes": sorted(exclusions),
        "counts": {t: len(r) for t, r in inserts.items()},
        "balance_adjustments": {str(u): -d for u, d in totals.items() if d},
        "preserved": {t: len(target[t]) for t in TARGET_TABLES},
    }


def read_receipt(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT input_hash, plan_hash, result FROM reconciliation_receipt WHERE id = 'v3-final'"
        )
        return cur.fetchone()


def apply_plan(conn, source, policy, transcripts, plan):
    """Caller owns the transaction. Locks and validation precede any insert."""
    with conn.cursor() as cur:
        cur.execute("SET LOCAL lock_timeout = '5s'")
        cur.execute(
            sql.SQL("LOCK TABLE {} IN EXCLUSIVE MODE").format(
                sql.SQL(", ").join(
                    sql.Identifier(t)
                    for t in (*TARGET_TABLES, "reconciliation_receipt")
                )
            )
        )
    receipt = read_receipt(conn)
    if receipt:
        require(
            receipt[0] == input_hash(source, policy, transcripts)
            and receipt[1] == digest(plan),
            "Reconciliation already completed with different inputs or plan",
        )
        return {"already_applied": True, "result": receipt[2]}
    before = snapshot(conn, TARGET_TABLES)
    require(
        build_plan(source, before, policy, transcripts) == plan,
        "Plan is stale or edited; regenerate and review",
    )
    with conn.cursor() as cur:
        for table in INSERT_TABLES:
            for record in plan["inserts"][table]:
                record = dict(record)
                if table == "credits_ledger" and record["created_at"] is None:
                    cur.execute("SELECT now() AT TIME ZONE 'UTC'")
                    record["created_at"] = cur.fetchone()[0]
                columns = list(record)
                cur.execute(
                    sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                        sql.Identifier(table),
                        sql.SQL(", ").join(map(sql.Identifier, columns)),
                        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
                    ),
                    [
                        Json(record[c])
                        if isinstance(record[c], (dict, list))
                        else record[c]
                        for c in columns
                    ],
                )
        after = snapshot(conn, TARGET_TABLES)
        for table in TARGET_TABLES:
            # All old rows must still exist byte-for-byte in canonical JSON.
            counts = Counter(digest(r) for r in after[table])
            require(
                not (Counter(digest(r) for r in before[table]) - counts),
                f"Existing {table} changed",
            )
            require(
                len(after[table])
                == len(before[table]) + len(plan["inserts"].get(table, [])),
                f"Unexpected {table} count",
            )
        for user in before["users"]:
            uid = user["id"]
            delta = sum(
                r["delta"] for r in after["credits_ledger"] if r["user_id"] == uid
            ) - sum(r["delta"] for r in before["credits_ledger"] if r["user_id"] == uid)
            require(delta == 0, f"Ledger offset changed: user {uid}")
        result = {
            k: plan[k]
            for k in (
                "maps",
                "counts",
                "balance_adjustments",
                "excluded_notes",
                "preserved",
            )
        }
        # setval is not rolled back by PostgreSQL; failure can leave harmless gaps.
        # Never lower a sequence, including one already ahead after deleted rows.
        for table in INSERT_TABLES:
            if table == "library_items" or not plan["inserts"][table]:
                continue
            cur.execute("SELECT pg_get_serial_sequence(%s, 'id')", (table,))
            sequence = cur.fetchone()[0]
            require(sequence is not None, f"Missing sequence: {table}")
            cur.execute(
                sql.SQL("SELECT last_value FROM {}").format(
                    sql.Identifier(*sequence.split("."))
                )
            )
            last = cur.fetchone()[0]
            cur.execute(sql.SQL("SELECT max(id) FROM {}").format(sql.Identifier(table)))
            cur.execute(
                "SELECT setval(%s, %s, true)", (sequence, max(last, cur.fetchone()[0]))
            )
        result["target_after_hash"] = digest(snapshot(conn, TARGET_TABLES))
        cur.execute(
            "INSERT INTO reconciliation_receipt(id, input_hash, plan_hash, result) VALUES ('v3-final', %s, %s, %s)",
            (plan["input_hash"], digest(plan), Json(result)),
        )
    return {"already_applied": False, "result": result}


def write_private(path, value):
    # Refuse overwrite and create private from the first byte (not chmod later).
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write("\n")


def load_json(path):
    return json.loads(Path(path).read_text())


def connect(env_name):
    dsn = os.environ.get(env_name)
    require(bool(dsn), f"Missing connection environment variable: {env_name}")
    conn = psycopg2.connect(dsn)
    require(conn.server_version >= 170000, "PostgreSQL 17 or later required")
    return conn


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("export", "plan", "apply"))
    parser.add_argument("--source")
    parser.add_argument("--policy")
    parser.add_argument(
        "--transcripts",
        help="Local JSON object keyed by video ID; use {} when none needed",
    )
    parser.add_argument("--plan")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    try:
        require(
            not Path(args.out).exists(), "Output already exists; use a new output path"
        )
        if args.command == "export":
            with connect("RECONCILE_SOURCE_DSN") as conn:
                conn.set_session(readonly=True, isolation_level="REPEATABLE READ")
                result = snapshot(conn, SOURCE_TABLES)
        else:
            require(
                all((args.source, args.policy, args.transcripts)),
                "--source, --policy, --transcripts required",
            )
            source, policy, transcripts = map(
                load_json, (args.source, args.policy, args.transcripts)
            )
            with connect("RECONCILE_TARGET_DSN") as conn:
                if args.command == "plan":
                    conn.set_session(readonly=True, isolation_level="REPEATABLE READ")
                    require(
                        read_receipt(conn) is None,
                        "Already reconciled; use apply with the original plan to verify its receipt",
                    )
                    result = build_plan(
                        source, snapshot(conn, TARGET_TABLES), policy, transcripts
                    )
                else:
                    require(args.plan is not None, "--plan required")
                    # Receipt persists even if writing the result file later fails.
                    result = apply_plan(
                        conn, source, policy, transcripts, load_json(args.plan)
                    )
        write_private(args.out, result)
        print("Wrote private reconciliation artifact")
    except (Conflict, psycopg2.Error, OSError, ValueError, KeyError, TypeError):
        # Provider/driver errors can contain private SQL values. Keep them off stdout.
        # Conflict messages are deliberately identifiers-only.
        import sys

        error = sys.exc_info()[1]
        parser.exit(
            2,
            f"{error}\n"
            if isinstance(error, Conflict)
            else "Reconciliation failed; check inputs, schema, connectivity, and output path.\n",
        )


if __name__ == "__main__":
    main()
