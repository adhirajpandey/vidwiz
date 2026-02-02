import pytest
from unittest.mock import patch, MagicMock
import os
import sys

# Mock AWS Lambda Powertools
class MockLogger:
    def inject_lambda_context(self, log_event=True):
        def decorator(func):
            return func
        return decorator

    def info(self, msg, extra=None): pass
    def warning(self, msg, extra=None): pass
    def error(self, msg, extra=None): pass
    def debug(self, msg, extra=None): pass
    def exception(self, msg, extra=None): pass

# Mock Envelopes and Utilities
class MockEnvelopes:
    SqsEnvelope = MagicMock()

class MockUtilities:
    BaseModel = MagicMock
    envelopes = MockEnvelopes
    event_parser = MagicMock(return_value=lambda x: x)
    typing = MagicMock()
    LambdaContext = MagicMock

# Setup mocks before importing lambdas
module_patcher = patch.dict(sys.modules, {
    "aws_lambda_powertools": MagicMock(Logger=MockLogger),
    "aws_lambda_powertools.utilities.parser": MockUtilities,
    "aws_lambda_powertools.utilities.typing": MockUtilities,
})

@pytest.fixture(autouse=True)
def mock_env_vars():
    """Set environment variables required by lambdas"""
    env_vars = {
        "GEMINI_API_KEY": "test_key",
        "S3_BUCKET_NAME": "test_bucket",
        "VIDWIZ_ENDPOINT": "http://test-endpoint",
        "VIDWIZ_TOKEN": "test_token",
        "SQS_QUEUE_URL": "http://sqs-url",
        "ADMIN_AUTH_TOKEN": "admin_token",
        "VIDWIZ_HOST": "vidwiz.test"
    }
    with patch.dict(os.environ, env_vars):
        yield

class TestGenAINoteLambda:
    @pytest.fixture
    def gen_ai_lambda(self, mock_env_vars):
        # We need to ensure we're importing the renamed file
        # Check if the renamed file is in sys.modules and remove it if so to force reload
        if "vidwiz.lambdas.gen_ai_note" in sys.modules:
            del sys.modules["vidwiz.lambdas.gen_ai_note"]

        with module_patcher:
            import vidwiz.lambdas.gen_ai_note as gen_ai
            return gen_ai

    def test_format_timestamp_in_seconds(self, gen_ai_lambda):
        assert gen_ai_lambda.format_timestamp_in_seconds("00:01:30") == 90
        assert gen_ai_lambda.format_timestamp_in_seconds("01:00") == 60

        with pytest.raises(Exception):
            gen_ai_lambda.format_timestamp_in_seconds("invalid")

    def test_get_transcript_from_s3_success(self, gen_ai_lambda):
        mock_s3 = MagicMock()
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=lambda: b'[{"text": "hello", "offset": 1.0}]')
        }

        with patch("boto3.client", return_value=mock_s3):
            transcript = gen_ai_lambda.get_transcript_from_s3("video1")
            assert len(transcript) == 1
            assert transcript[0]["text"] == "hello"

    def test_get_relevant_transcript(self, gen_ai_lambda):
        transcript = [
            {"offset": 10.0, "text": "before"},
            {"offset": 20.0, "text": "target"},
            {"offset": 30.0, "text": "after"}
        ]

        # Test exact match logic
        context = gen_ai_lambda.get_relevant_transcript(transcript, "00:00:20")
        assert context.text == "target"

        # Test no relevant segments
        context = gen_ai_lambda.get_relevant_transcript(transcript, "01:00:00")
        assert context is None

    def test_generate_note_using_llm(self, gen_ai_lambda):
        mock_context = MagicMock()
        mock_context.before = []
        mock_context.after = []
        mock_context.text = "test content"

        with patch.object(gen_ai_lambda, "gemini_api_call", return_value="Generated Note"):
            note = gen_ai_lambda.generate_note_using_llm("Title", "00:01:00", mock_context)
            assert note == "Generated Note"

    def test_is_valid_note_length(self, gen_ai_lambda):
        # We need to set the global variables directly since they are read from env at import time
        gen_ai_lambda.MIN_NOTE_LENGTH = 5
        gen_ai_lambda.MAX_NOTE_LENGTH = 20

        assert gen_ai_lambda.is_valid_note_length("Valid Note") is True

        # "Too" is 3 chars < 5
        assert gen_ai_lambda.is_valid_note_length("Too") is False

        assert gen_ai_lambda.is_valid_note_length("This note is way too long for the limit") is False

    def test_lambda_handler_process_flow(self, gen_ai_lambda):
        mock_note = MagicMock()
        mock_note.id = "note1"
        mock_note.video_id = "vid1"
        mock_note.timestamp = "00:01:00"
        mock_note.video.title = "Test Video"

        with patch.object(gen_ai_lambda, "get_transcript_from_s3", return_value=[{"offset": 60.0, "text": "content"}]), \
             patch.object(gen_ai_lambda, "get_valid_ai_note", return_value="AI Note"), \
             patch.object(gen_ai_lambda, "update_vidwiz_note") as mock_update:

            gen_ai_lambda.lambda_handler([mock_note], MagicMock())

            mock_update.assert_called_with("note1", "AI Note")

class TestPushNotesLambda:
    @pytest.fixture
    def push_lambda(self, mock_env_vars):
        if "vidwiz.lambdas.push_notes_to_queue" in sys.modules:
            del sys.modules["vidwiz.lambdas.push_notes_to_queue"]

        with module_patcher:
            import vidwiz.lambdas.push_notes_to_queue as push_notes
            return push_notes

    def test_extract_valid_video_id(self, push_lambda):
        assert push_lambda.extract_valid_video_id("transcripts/vid123.json") == "vid123"
        assert push_lambda.extract_valid_video_id("invalid/path") == "path" # Basic split logic

    def test_fetch_all_notes_success(self, push_lambda):
        # Patch `requests` where it is imported in `vidwiz.lambdas.push_notes_to_queue`
        # Because we're dynamically importing in the fixture, we need to ensure we patch the module's attribute
        with patch.object(push_lambda.requests, "get") as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {"notes": [{"id": 1}]}

            notes = push_lambda.fetch_all_notes("vid1")
            assert len(notes) == 1
            assert notes[0]["id"] == 1

    def test_push_notes_to_sqs_batch(self, push_lambda):
        mock_sqs = MagicMock()
        mock_sqs.send_message_batch.return_value = {"Successful": ["msg1"], "Failed": []}

        notes = [{"id": i} for i in range(15)] # 15 notes -> 2 batches

        with patch("boto3.client", return_value=mock_sqs):
            result = push_lambda.push_notes_to_sqs_batch(notes)

            assert result["batches"] == 2
            assert mock_sqs.send_message_batch.call_count == 2

    def test_lambda_handler_full_flow(self, push_lambda):
        event = {
            "Records": [{
                "s3": {
                    "object": {"key": "transcripts/vid1.json"}
                }
            }]
        }

        with patch.object(push_lambda, "fetch_all_notes", return_value=[{"id": 1}]), \
             patch.object(push_lambda, "push_notes_to_sqs_batch") as mock_push:

            push_lambda.lambda_handler(event, MagicMock())

            mock_push.assert_called_once()
