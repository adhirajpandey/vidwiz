import pytest
import json
import importlib
from unittest.mock import patch
from vidwiz.lambdas import gen_note
from vidwiz.lambdas.gen_note import (
    lambda_handler,
    check_authorization,
    format_timestamp_in_seconds,
    get_relevant_transcript,
)

# Test constants
TEST_BASE_URL = "http://test-server.com"
TEST_AUTH_TOKEN = "test_token"
TEST_GEMINI_KEY = "test_gemini_key"
TEST_RAPIDAPI_KEY = "test_rapidapi_key"
TEST_VIDEO_ID = "test_video"
TEST_VIDEO_TITLE = "Test Video Title"
TEST_NOTE_TIMESTAMP = "1:23"
TEST_NOTE_ID = "123"


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables and reload the lambda module."""
    monkeypatch.setenv("BASE_URL", TEST_BASE_URL)
    monkeypatch.setenv("AUTH_TOKEN", TEST_AUTH_TOKEN)
    monkeypatch.setenv("PREFERRED_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", TEST_GEMINI_KEY)
    monkeypatch.setenv("RAPIDAPI_KEY", TEST_RAPIDAPI_KEY)
    importlib.reload(gen_note)


@pytest.fixture
def api_gateway_event():
    """Provide a sample API Gateway event fixture."""
    return {
        "headers": {"authorization": f"Bearer {TEST_AUTH_TOKEN}"},
        "body": json.dumps(
            {
                "id": TEST_NOTE_ID,
                "video_id": TEST_VIDEO_ID,
                "video_title": TEST_VIDEO_TITLE,
                "note_timestamp": TEST_NOTE_TIMESTAMP,
            }
        ),
    }


def test_format_timestamp_in_seconds():
    """Test the conversion of timestamp strings to seconds."""
    assert format_timestamp_in_seconds("1:23") == 83
    assert format_timestamp_in_seconds("10:05") == 605
    assert format_timestamp_in_seconds("0:00") == 0


def test_check_authorization(mock_env_vars):
    """Test the authorization logic with correct and incorrect tokens."""
    assert check_authorization({"authorization": f"Bearer {TEST_AUTH_TOKEN}"}) is True
    assert check_authorization({"authorization": "Bearer wrong_token"}) is False
    assert check_authorization({}) is False


def test_get_relevant_transcript():
    """Test the extraction of relevant transcript portions."""
    transcript = [
        {"offset": 10, "text": "part 1"},
        {"offset": 20, "text": "part 2"},
        {"offset": 80, "text": "part 3"},
        {"offset": 90, "text": "part 4"},
    ]
    # Test case where a relevant transcript is found for "1:23" (83 seconds)
    relevant_transcript_json = get_relevant_transcript(transcript, "1:23")
    assert relevant_transcript_json is not None
    relevant_transcript = json.loads(relevant_transcript_json)
    assert relevant_transcript["text"] == "part 3"

    # Test case where no relevant transcript is found
    assert get_relevant_transcript(transcript, "20:00") is None


@patch("vidwiz.lambdas.gen_note.requests.patch")
@patch("vidwiz.lambdas.gen_note.gemini_api_call")
@patch("vidwiz.lambdas.gen_note.get_transcript")
def test_lambda_handler_success(
    mock_get_transcript, mock_gemini_call, mock_patch, api_gateway_event, mock_env_vars
):
    """Test the successful execution of the lambda handler."""
    # Mock external calls
    mock_get_transcript.return_value = [
        {"offset": 83, "text": "This is a test transcript."}
    ]
    mock_gemini_call.return_value = "This is a test AI note."
    mock_patch.return_value.status_code = 200
    mock_patch.return_value.json.return_value = {
        "id": "123",
        "ai_note": "This is a test AI note.",
    }

    response = lambda_handler(api_gateway_event, None)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["message"] == "Successfully generated and updated AI note"


def test_lambda_handler_unauthorized(api_gateway_event, mock_env_vars):
    """Test that the lambda handler returns 401 for an invalid token."""
    api_gateway_event["headers"]["authorization"] = "Bearer wrong_token"
    response = lambda_handler(api_gateway_event, None)
    assert response["statusCode"] == 401
    assert "Unauthorized" in response["body"]


@patch("vidwiz.lambdas.gen_note.check_authorization", return_value=True)
def test_lambda_handler_missing_data(_, api_gateway_event, mock_env_vars):
    """Test that the lambda handler returns 400 if the request body is empty."""
    api_gateway_event["body"] = "{}"
    response = lambda_handler(api_gateway_event, None)
    assert response["statusCode"] == 400
    assert "No data provided" in response["body"]


@patch("vidwiz.lambdas.gen_note.get_transcript")
@patch("vidwiz.lambdas.gen_note.check_authorization", return_value=True)
def test_lambda_handler_transcript_not_found(
    _, mock_get_transcript, api_gateway_event, mock_env_vars
):
    """Test that the lambda handler returns 404 if the transcript is not found."""
    mock_get_transcript.return_value = None
    response = lambda_handler(api_gateway_event, None)
    assert response["statusCode"] == 404
    assert "Transcript not found" in response["body"]


@patch("vidwiz.lambdas.gen_note.get_transcript")
@patch("vidwiz.lambdas.gen_note.check_authorization", return_value=True)
def test_lambda_handler_no_relevant_transcript(
    _, mock_get_transcript, api_gateway_event, mock_env_vars
):
    """Test that the lambda handler returns 404 if no relevant transcript is found."""
    mock_get_transcript.return_value = [{"offset": 5000, "text": "some distant text"}]
    response = lambda_handler(api_gateway_event, None)
    assert response["statusCode"] == 404
    assert "No relevant transcript found" in response["body"]


@patch("vidwiz.lambdas.gen_note.gemini_api_call")
@patch("vidwiz.lambdas.gen_note.get_transcript")
@patch("vidwiz.lambdas.gen_note.check_authorization", return_value=True)
def test_lambda_handler_ai_note_fails(
    _, mock_get_transcript, mock_gemini_call, api_gateway_event, mock_env_vars
):
    """Test that the lambda handler returns 500 if AI note generation fails."""
    mock_get_transcript.return_value = [
        {"offset": 83, "text": "This is a test transcript."}
    ]
    mock_gemini_call.return_value = None
    response = lambda_handler(api_gateway_event, None)
    assert response["statusCode"] == 500
    assert "Failed to generate AI note" in response["body"]


@patch("vidwiz.lambdas.gen_note.requests.patch")
@patch("vidwiz.lambdas.gen_note.gemini_api_call")
@patch("vidwiz.lambdas.gen_note.get_transcript")
@patch("vidwiz.lambdas.gen_note.check_authorization", return_value=True)
def test_lambda_handler_update_fails(
    _,
    mock_get_transcript,
    mock_gemini_call,
    mock_patch,
    api_gateway_event,
    mock_env_vars,
):
    """Test that the lambda handler returns 500 if updating the note fails."""
    mock_get_transcript.return_value = [
        {"offset": 83, "text": "This is a test transcript."}
    ]
    mock_gemini_call.return_value = "This is a test AI note."
    mock_patch.side_effect = Exception("Failed to update")

    response = lambda_handler(api_gateway_event, None)

    assert response["statusCode"] == 500
    assert "Failed to update" in response["body"]
