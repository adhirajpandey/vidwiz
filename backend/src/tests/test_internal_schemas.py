import pytest
from pydantic import ValidationError

from src.internal.schemas import TaskResultRequest, TranscriptWrite, SummaryWrite


def test_task_result_request_validates_transcript_items():
    with pytest.raises(ValidationError):
        TaskResultRequest.model_validate(
            {"video_id": "abc123DEF45", "success": True, "transcript": ["bad"]}
        )

    with pytest.raises(ValidationError):
        TaskResultRequest.model_validate(
            {"video_id": "abc123DEF45", "success": True, "transcript": [{"offset": 0}]}
        )


def test_task_result_request_validates_metadata():
    with pytest.raises(ValidationError):
        TaskResultRequest.model_validate(
            {"video_id": "abc123DEF45", "success": True, "metadata": "bad"}
        )

    TaskResultRequest.model_validate(
        {"video_id": "abc123DEF45", "success": True, "metadata": {"title": "Video"}}
    )


def test_transcript_write_validates_items():
    with pytest.raises(ValidationError):
        TranscriptWrite.model_validate({"transcript": ["bad"]})

    with pytest.raises(ValidationError):
        TranscriptWrite.model_validate({"transcript": [{"offset": 0}]})


def test_summary_write_limits_length():
    SummaryWrite.model_validate({"summary": "ok"})


def test_summary_write_validates_suggested_questions():
    payload = SummaryWrite.model_validate(
        {
            "summary": "ok",
            "miscellaneous_data": {
                "suggested_questions": [
                    "  What is the first idea?  ",
                    "How is the idea supported?",
                    "What conclusion is reached?",
                ]
            },
        }
    )

    assert payload.miscellaneous_data is not None
    assert payload.miscellaneous_data.suggested_questions[0] == (
        "What is the first idea?"
    )

    with pytest.raises(ValidationError):
        SummaryWrite.model_validate(
            {
                "summary": "ok",
                "miscellaneous_data": {
                    "suggested_questions": ["Duplicate?", "duplicate?", "Different?"]
                },
            }
        )

    with pytest.raises(ValidationError):
        SummaryWrite.model_validate(
            {
                "summary": "ok",
                "miscellaneous_data": {"suggested_questions": ["Only one?"]},
            }
        )
