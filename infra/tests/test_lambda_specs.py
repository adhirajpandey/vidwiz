from vidwiz_infra.bundling import SHARED_WORKER_DIR, SharedWorkerPackageHooks
from vidwiz_infra.lambda_specs import LAMBDA_SPECS


def test_lambda_specs_map_each_function_to_a_self_contained_entry() -> None:
    assert len(LAMBDA_SPECS) == 3
    assert {
        (spec.key, spec.construct_id, spec.function_name) for spec in LAMBDA_SPECS
    } == {
        (
            "transcript_dispatcher",
            "TranscriptDispatcher",
            "vidwiz-prod-transcript-dispatcher",
        ),
        ("ai_note_worker", "AiNoteWorker", "vidwiz-prod-ai-note-worker"),
        ("ai_summary_worker", "AiSummaryWorker", "vidwiz-prod-ai-summary-worker"),
    }

    for spec in LAMBDA_SPECS:
        assert (spec.source / "handler.py").is_file()
        assert (spec.source / "pyproject.toml").is_file()
        assert (spec.source / "uv.lock").is_file()
        assert not (spec.source / "requirements.txt").exists()


def test_ai_worker_bundling_copies_the_shared_package() -> None:
    hooks = SharedWorkerPackageHooks()

    assert (SHARED_WORKER_DIR / "vidwiz_worker" / "__init__.py").is_file()
    assert hooks.before_bundling("/asset-input", "/asset-output") == [
        "cp -R /asset-shared/vidwiz_worker /asset-input/vidwiz_worker"
    ]
    assert hooks.after_bundling("/asset-input", "/asset-output") == []
