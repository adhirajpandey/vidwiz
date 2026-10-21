"""Synthetic PostgreSQL tests; no production copies or external APIs."""

from copy import deepcopy
import hashlib
import json
import os
import subprocess
import sys

import psycopg2
import pytest

from src.management import reconcile as r

T0 = "2026-01-01T00:00:00+00:00"
T1 = "2026-02-01T00:00:00+00:00"


@pytest.fixture
def reconciliation(engine):
    conn = psycopg2.connect(engine.url.render_as_string(hide_password=False))
    with conn.cursor() as cur:
        cur.execute(
            "TRUNCATE "
            + ", ".join((*r.TARGET_TABLES, "reconciliation_receipt"))
            + " RESTART IDENTITY CASCADE"
        )
        cur.execute("""
            INSERT INTO users(id,email,name,password_hash,credits_balance,created_at)
            VALUES (1,'owner@example.test','Owner','v3-password',94,'2026-01-01'),
                   (2,'tester@example.test','Tester','test-password',70,'2026-02-01');
            INSERT INTO videos(id,video_id,title,created_at,updated_at,transcript_status,overview_status)
            VALUES (1,'shared','Shared','2026-01-01','2026-01-01','unavailable','no_transcript'),
                   (2,'v3-only','Test','2026-02-01','2026-02-01','unavailable','no_transcript');
            INSERT INTO moments(id,user_id,video_id,at_seconds,ai_text,source,ai_status,resolve_status,created_at,updated_at)
            VALUES (10,1,'shared',60,'Old AI','legacy','ready','resolved','2026-01-01','2026-01-01'),
                   (11,2,'v3-only',12,NULL,'api','not_requested','resolved','2026-02-01','2026-02-01');
            INSERT INTO credits_ledger(id,user_id,delta,reason,ref_type,ref_id,created_at)
            VALUES (1,1,-1,'ai_moment','moment','10','2026-01-01'),
                   (2,2,100,'signup_grant','user','2','2026-02-01');
            INSERT INTO library_items(user_id,video_id,added_at) VALUES (1,'shared','2026-01-01');
        """)
        cur.execute(
            "INSERT INTO api_tokens(user_id,name,token_hash,token_hint,revoked_at) VALUES (1,'Legacy token',%s,'fake','2026-02-01')",
            (hashlib.sha256(b"legacy-token").hexdigest(),),
        )
    target = r.snapshot(conn, r.TARGET_TABLES)
    source = {t: [] for t in r.SOURCE_TABLES}
    source["users"] = [
        dict(
            target["users"][0],
            password_hash="old-password",
            credits_balance=125,
            long_term_token="legacy-token",
        )
    ]
    source["videos"] = [
        dict(
            id=1,
            video_id="shared",
            title="Shared",
            video_metadata=None,
            summary=None,
            miscellaneous_data={},
            created_at=T0,
            updated_at=T0,
            transcript_available=False,
        ),
        dict(
            id=2,
            video_id="new-video",
            title=None,
            video_metadata={"title": "Metadata title"},
            summary="Old summary",
            miscellaneous_data={},
            created_at=T1,
            updated_at=T1,
            transcript_available=True,
        ),
    ]
    source["notes"] = [
        dict(
            id=10,
            user_id=1,
            video_id="shared",
            timestamp="1:00",
            text="Old AI",
            generated_by_ai=True,
            created_at=T0,
            updated_at=T0,
        ),
        dict(
            id=11,
            user_id=1,
            video_id="new-video",
            timestamp="1:40",
            text="New AI",
            generated_by_ai=True,
            created_at=T1,
            updated_at=T1,
        ),
        dict(
            id=9,
            user_id=1,
            video_id="shared",
            timestamp="0:10",
            text="Deleted",
            generated_by_ai=False,
            created_at=T0,
            updated_at=T0,
        ),
    ]
    source["credits_ledger"] = [
        dict(
            id=1,
            user_id=1,
            delta=-1,
            reason="ai_note",
            ref_type="note",
            ref_id="10",
            created_at=T0,
        ),
        dict(
            id=2,
            user_id=1,
            delta=-1,
            reason="ai_note",
            ref_type="note",
            ref_id="11",
            created_at=T1,
        ),
    ]
    policy = {
        "keep_v3_accounts_and_balances": True,
        "exclude_notes": {"9": r.digest(source["notes"][2])},
        "import_notes": {"11": r.digest(source["notes"][1])},
    }
    transcripts = {
        "new-video": [{"text": "The real quote", "offset": 99, "duration": 3}]
    }
    try:
        yield conn, source, target, policy, transcripts
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE "
                + ", ".join((*r.TARGET_TABLES, "reconciliation_receipt"))
                + " RESTART IDENTITY CASCADE"
            )
        conn.commit()
        conn.close()


def test_import_collision_history_preservation_and_repeat(reconciliation):
    conn, source, target, policy, transcripts = reconciliation
    plan = r.build_plan(source, target, policy, transcripts)
    assert plan["maps"]["notes"]["11"] == 12
    assert plan["maps"]["videos"]["2"] == 3
    assert plan["balance_adjustments"] == {"1": 1}
    assert plan["counts"] == dict(
        videos=1, moments=1, library_items=1, transcript_chunks=1, credits_ledger=2
    )
    result = r.apply_plan(conn, source, policy, transcripts, plan)
    after = r.snapshot(conn, r.TARGET_TABLES)
    assert result["already_applied"] is False
    assert after["users"] == target["users"]
    assert after["api_tokens"] == target["api_tokens"]  # Revoked token stays revoked.
    imported = next(x for x in after["moments"] if x["id"] == 12)
    assert imported["quote"] == "The real quote"
    assert imported["created_at"] == T1 and imported["updated_at"] == T1
    assert not any(x["id"] == 9 for x in after["moments"])
    assert next(x for x in after["videos"] if x["id"] == 3)["title"] == "Metadata title"
    assert any(
        x["ref_id"] == "12" and x["delta"] == -1 for x in after["credits_ledger"]
    )
    assert (
        r.apply_plan(conn, source, policy, transcripts, plan)["already_applied"] is True
    )
    assert r.snapshot(conn, r.TARGET_TABLES) == after
    # Sequence is advanced beyond all explicit IDs, including a collision.
    with conn.cursor() as cur:
        cur.execute("SELECT nextval('moments_id_seq')")
        assert cur.fetchone()[0] > 12


@pytest.mark.parametrize(
    "change",
    [
        "legacy_edit",
        "legacy_delete",
        "new_note",
        "password_identity",
        "token",
        "new_payment",
        "message",
        "task",
        "missing_transcript",
        "exclusion",
        "ledger",
    ],
)
def test_unreviewed_conflicts_stop(reconciliation, change):
    _, source, target, policy, transcripts = reconciliation
    if change == "legacy_edit":
        source["notes"][0]["text"] = "Changed"
    if change == "legacy_delete":
        source["notes"].pop(0)
    if change == "new_note":
        source["notes"].append(dict(source["notes"][1], id=22))
    if change == "password_identity":
        source["users"][0]["email"] = "different@example.test"
    if change == "token":
        source["users"][0]["long_term_token"] = "rotated"
    if change == "new_payment":
        source["credit_purchases"].append({"id": 99})
    if change == "message":
        source["messages"].append({"id": 99})
    if change == "task":
        source["tasks"].append({"status": "PENDING", "retry_count": 0})
    if change == "missing_transcript":
        transcripts.clear()
    if change == "exclusion":
        source["notes"][2]["text"] = "Changed after decision"
    if change == "ledger":
        source["credits_ledger"][0]["delta"] = -99
    with pytest.raises(r.Conflict):
        r.build_plan(source, target, policy, transcripts)


def test_stale_and_edited_plan_make_no_writes(reconciliation):
    conn, source, target, policy, transcripts = reconciliation
    plan = r.build_plan(source, target, policy, transcripts)
    altered = deepcopy(plan)
    altered["inserts"]["moments"][0]["ai_text"] = "Injected"
    with pytest.raises(r.Conflict, match="stale or edited"):
        r.apply_plan(conn, source, policy, transcripts, altered)
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET credits_balance=93 WHERE id=1")
    before = r.snapshot(conn, r.TARGET_TABLES)
    with pytest.raises(r.Conflict, match="stale or edited"):
        r.apply_plan(conn, source, policy, transcripts, plan)
    assert r.snapshot(conn, r.TARGET_TABLES) == before
    assert r.read_receipt(conn) is None


def test_failure_rolls_back_records_and_receipt(reconciliation, monkeypatch):
    conn, source, target, policy, transcripts = reconciliation
    plan = r.build_plan(source, target, policy, transcripts)
    original = r.snapshot
    calls = 0

    def fail_after_writes(*args):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic failure")
        return original(*args)

    with conn.cursor() as cur:
        cur.execute("SAVEPOINT before_import")
    monkeypatch.setattr(r, "snapshot", fail_after_writes)
    with pytest.raises(RuntimeError):
        r.apply_plan(conn, source, policy, transcripts, plan)
    with conn.cursor() as cur:
        cur.execute("ROLLBACK TO SAVEPOINT before_import")
    assert original(conn, r.TARGET_TABLES) == target
    assert r.read_receipt(conn) is None


def test_completed_import_rejects_changed_source(reconciliation):
    conn, source, target, policy, transcripts = reconciliation
    plan = r.build_plan(source, target, policy, transcripts)
    r.apply_plan(conn, source, policy, transcripts, plan)
    source["notes"][1]["text"] = "Changed"
    with pytest.raises(r.Conflict, match="already completed"):
        r.apply_plan(conn, source, policy, transcripts, plan)


def test_plan_has_no_side_effects_and_preserves_input(reconciliation):
    _, source, target, policy, transcripts = reconciliation
    before = deepcopy((source, target, policy, transcripts))
    assert r.build_plan(source, target, policy, transcripts) == r.build_plan(
        source, target, policy, transcripts
    )
    assert before == (source, target, policy, transcripts)


def test_private_artifacts_refuse_overwrite(tmp_path):
    path = tmp_path / "private.json"
    r.write_private(path, {"x": 1})
    assert path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        r.write_private(path, {"x": 2})
    assert json.loads(path.read_text()) == {"x": 1}


def test_cli_help_needs_no_app_credentials():
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "SYSTEMROOT")}
    result = subprocess.run(
        [sys.executable, "-m", "src.management.reconcile", "--help"],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_committed_receipt_survives_reconnect_and_cli_retry(reconciliation, tmp_path):
    conn, source, target, policy, transcripts = reconciliation
    plan = r.build_plan(source, target, policy, transcripts)
    conn.commit()  # Publish only synthetic fixture data to the subprocess.
    files = {}
    for key, value in dict(
        source=source, policy=policy, transcripts=transcripts, plan=plan
    ).items():
        files[key] = tmp_path / (key + ".json")
        r.write_private(files[key], value)
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "SYSTEMROOT")}
    env["RECONCILE_TARGET_DSN"] = os.environ["TEST_DB_URL"]
    args = [sys.executable, "-m", "src.management.reconcile", "apply"]
    for key, path in files.items():
        args.extend(["--" + key, str(path)])
    result = subprocess.run(
        args + ["--out", str(tmp_path / "result.json")],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (
        json.loads((tmp_path / "result.json").read_text())["already_applied"] is False
    )
    before = r.snapshot(conn, r.TARGET_TABLES)
    result = subprocess.run(
        args + ["--out", str(tmp_path / "retry.json")],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads((tmp_path / "retry.json").read_text())["already_applied"] is True
    assert r.snapshot(conn, r.TARGET_TABLES) == before


def test_existing_chunks_and_library_activity_survive(reconciliation):
    conn, source, _, policy, transcripts = reconciliation
    # Import another moment onto an existing video. Its derived data stays intact.
    source["notes"][1]["video_id"] = "shared"
    source["videos"] = source["videos"][:1]
    source["videos"][0]["transcript_available"] = True
    policy["import_notes"]["11"] = r.digest(source["notes"][1])
    transcripts["shared"] = transcripts.pop("new-video")
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE videos SET transcript_status='ready' WHERE video_id='shared'"
        )
        cur.execute(
            "INSERT INTO transcript_chunks(id,video_id,idx,start_seconds,end_seconds,text) VALUES (25,'shared',0,90,110,'Existing citation')"
        )
    target = r.snapshot(conn, r.TARGET_TABLES)
    plan = r.build_plan(source, target, policy, transcripts)
    assert plan["counts"]["transcript_chunks"] == 0
    assert plan["counts"]["library_items"] == 0
    r.apply_plan(conn, source, policy, transcripts, plan)
    after = r.snapshot(conn, r.TARGET_TABLES)
    assert after["transcript_chunks"] == target["transcript_chunks"]
    assert after["library_items"] == target["library_items"]


def test_deleted_note_charge_is_kept_without_resurrecting_note(reconciliation):
    conn, source, _, policy, transcripts = reconciliation
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO credits_ledger(id,user_id,delta,reason,ref_type,ref_id,created_at) VALUES (3,1,-1,'ai_moment','moment','9','2026-01-01')"
        )
    source["credits_ledger"].append(
        dict(
            id=3,
            user_id=1,
            delta=-1,
            reason="ai_note",
            ref_type="note",
            ref_id="9",
            created_at=T0,
        )
    )
    target = r.snapshot(conn, r.TARGET_TABLES)
    plan = r.build_plan(source, target, policy, transcripts)
    assert plan["maps"]["credits_ledger"]["3"] == 3
    r.apply_plan(conn, source, policy, transcripts, plan)
    assert not any(m["id"] == 9 for m in r.snapshot(conn, r.TARGET_TABLES)["moments"])


def test_removed_production_token_never_revives_active_legacy_token(reconciliation):
    _, source, target, policy, transcripts = reconciliation
    source["users"][0]["long_term_token"] = None
    target["api_tokens"][0]["revoked_at"] = None
    with pytest.raises(r.Conflict, match="Legacy token removed"):
        r.build_plan(source, target, policy, transcripts)


def test_deleted_high_ids_are_not_reused(reconciliation):
    conn, source, _, policy, transcripts = reconciliation
    with conn.cursor() as cur:
        cur.execute("SELECT setval('moments_id_seq', 500, true)")
        cur.execute("SELECT setval('videos_id_seq', 600, true)")
    target = r.snapshot(conn, r.TARGET_TABLES)
    plan = r.build_plan(source, target, policy, transcripts)
    assert plan["maps"]["notes"]["11"] == 501
    assert plan["maps"]["videos"]["2"] == 601
    r.apply_plan(conn, source, policy, transcripts, plan)
    with conn.cursor() as cur:
        cur.execute("SELECT nextval('moments_id_seq')")
        assert cur.fetchone()[0] == 502
