from vidwiz_infra.lambda_specs import LAMBDA_SPECS


def test_lambda_specs_map_each_function_to_a_self_contained_entry() -> None:
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
        assert (spec.source / "requirements.txt").is_file()
