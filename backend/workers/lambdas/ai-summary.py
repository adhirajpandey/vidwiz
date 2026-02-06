from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import BaseModel, envelopes, event_parser
from aws_lambda_powertools.utilities.typing import LambdaContext
from typing import Dict, List, Optional
import json
import os
import time
import boto3
import requests

# Configuration constants
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
VIDWIZ_ENDPOINT = os.getenv("VIDWIZ_ENDPOINT")
VIDWIZ_TOKEN = os.getenv("VIDWIZ_TOKEN")
LLM_PROVIDER = (os.getenv("LLM_PROVIDER", "gemini") or "gemini").strip().lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_ENDPOINT = f"{GEMINI_BASE_URL}/{GEMINI_MODEL}:generateContent"

OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/responses")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-nano")

MAX_SUMMARY_LENGTH = int(os.getenv("MAX_SUMMARY_LENGTH", "800"))
MIN_SUMMARY_LENGTH = int(os.getenv("MIN_SUMMARY_LENGTH", "200"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

TRANSCRIPT_FETCH_MAX_RETRIES = int(os.getenv("TRANSCRIPT_FETCH_MAX_RETRIES", "5"))
TRANSCRIPT_FETCH_RETRY_DELAY = int(os.getenv("TRANSCRIPT_FETCH_RETRY_DELAY", "2"))


assert S3_BUCKET_NAME, "S3_BUCKET_NAME is not set"
assert VIDWIZ_ENDPOINT, "VIDWIZ_ENDPOINT is not set"
assert VIDWIZ_TOKEN, "VIDWIZ_TOKEN is not set"
assert LLM_PROVIDER in ("openai", "gemini"), "LLM_PROVIDER must be 'openai' or 'gemini'"
assert GEMINI_API_KEY or OPENAI_API_KEY, "At least one of GEMINI_API_KEY or OPENAI_API_KEY must be set"

# Initialize logger
logger = Logger()


# Data Models
class SummaryRequest(BaseModel):
    """
    SQS message payload for a summary generation request.

    Attributes:
        video_id: Unique identifier for the video to summarize.
    """

    video_id: str


# Prompt Template
def get_summary_generation_prompt_template(title: Optional[str], transcript: str) -> str:
    """
    Build the LLM prompt for generating a video summary.

    Args:
        title: Video title for context (optional; omitted from prompt if None).
        transcript: Full transcript text to summarize.

    Returns:
        Prompt string with length constraints and instructions.
    """
    title_block = f"Title: {title}\n\n" if title else ""
    return f"""Generate a clear and concise summary of the following video transcript.

The summary should be between {MIN_SUMMARY_LENGTH} and {MAX_SUMMARY_LENGTH} characters.
Capture the key ideas, explanations, and conclusions.
Do not include timestamps, formatting, bullet points, or extra commentary.

{title_block}Transcript:
{transcript}

Even if the transcript is in any language, generate the summary in English.
Return only the summary text, without any additional text or formatting.
"""


# Utility Functions
def get_s3_client():
    """
    Return a boto3 S3 client.

    Returns:
        boto3 S3 client instance.
    """
    return boto3.client("s3")


def get_transcript_from_s3(video_id: str, attempt: int = 1) -> Optional[List[Dict]]:
    """
    Fetch transcript from S3 with retry logic.

    Args:
        video_id: Unique identifier for the video; object key is transcripts/{video_id}.json.
        attempt: Current retry attempt (used internally).

    Returns:
        List of transcript segment dicts (with "text" and optionally "offset"), or None
        if the object is missing or max retries are exceeded.
    """
    transcript_key = f"transcripts/{video_id}.json"
    s3_client = get_s3_client()

    try:
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=transcript_key)
        transcript_data = json.loads(response["Body"].read().decode("utf-8"))
        if transcript_data is None:
            logger.warning("Transcript payload is null", extra={"video_id": video_id, "attempt": attempt})
            return None
        if not isinstance(transcript_data, list):
            logger.warning(
                "Transcript payload is not a list",
                extra={"video_id": video_id, "attempt": attempt, "payload_type": type(transcript_data).__name__},
            )
            return None
        logger.info("Successfully fetched transcript from S3", extra={"video_id": video_id, "attempt": attempt})
        return transcript_data
    except Exception as e:
        logger.warning(
            "Failed to get transcript from S3",
            extra={"video_id": video_id, "attempt": attempt, "max_retries": TRANSCRIPT_FETCH_MAX_RETRIES, "error": str(e)}
        )
        
        if attempt < TRANSCRIPT_FETCH_MAX_RETRIES:
            logger.info(
                "Retrying transcript fetch",
                extra={"video_id": video_id, "retry_delay_seconds": TRANSCRIPT_FETCH_RETRY_DELAY},
            )
            time.sleep(TRANSCRIPT_FETCH_RETRY_DELAY)
            return get_transcript_from_s3(video_id, attempt + 1)
        
        logger.error("Max retries reached for transcript fetch", extra={"video_id": video_id})
        return None


def get_video_metadata(video_id: str) -> Optional[Dict]:
    """
    Fetch video metadata from VidWiz API (e.g. title).

    Args:
        video_id: Unique identifier for the video.

    Returns:
        Response body as dict (e.g. {"title": "..."}) on 200, or None on error/non-200.
    """
    # Use api/v2/internal
    url = f"{VIDWIZ_ENDPOINT}/v2/internal/videos/{video_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {VIDWIZ_TOKEN}",
    }

    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error("Failed to get video metadata", extra={"video_id": video_id, "status": response.status_code})
            return None
    except Exception as e:
        logger.error("Error fetching video metadata", extra={"video_id": video_id, "error": str(e)})
        return None


def format_full_transcript(transcript: List[Dict]) -> str:
    """
    Join the entire transcript into one text blob for summarization.

    Args:
        transcript: List of segment dicts with at least a "text" key.

    Returns:
        Single string of all segment texts joined by spaces.
    """
    return " ".join(seg["text"] for seg in transcript)


def gemini_api_call(prompt: str) -> Optional[str]:
    """
    Call the Gemini API to generate text from a prompt.

    Args:
        prompt: Text prompt to send to the Gemini API.

    Returns:
        Generated text on success, or None on request/parse failure.
    """
    if not GEMINI_API_KEY:
        logger.error("Gemini API key is not set")
        return None
    logger.info("Making Gemini API call")
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        response = requests.post(
            GEMINI_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        response_data = response.json()
        if "error" in response_data:
            logger.error(
                "Gemini API returned error", extra={"error": response_data["error"]}
            )
            return None
        result = response_data["candidates"][0]["content"]["parts"][0]["text"]
        logger.info(
            "Successfully received response from Gemini",
            extra={"response_length": len(result)},
        )
        return result
    except Exception as e:
        logger.error("Gemini API request failed", extra={"error": str(e)})
        return None


def openai_api_call(prompt: str) -> Optional[str]:
    """
    Call the OpenAI API to generate text from a prompt.

    Args:
        prompt: Text prompt to send to the model.

    Returns:
        Generated text on success, or None on request/parse failure.
    """
    if not OPENAI_API_KEY:
        logger.error("OpenAI API key is not set")
        return None
    logger.info("Making OpenAI API call")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}",
    }
    payload = {"model": OPENAI_MODEL, "input": prompt}
    try:
        response = requests.post(
            OPENAI_API_URL, headers=headers, json=payload, timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        if "output_text" in data:
            return data["output_text"]
        text_parts = []
        for item in data.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if text := content.get("text"):
                        text_parts.append(text)
        return "".join(text_parts)
    except Exception as e:
        logger.error("OpenAI API request failed", extra={"error": str(e)})
        return None


def llm_call(prompt: str) -> Optional[str]:
    """
    Generate text using the configured LLM provider (default: gemini).

    Uses LLM_PROVIDER env: "gemini" or "openai". Requires the corresponding
    API key to be set. At least one of GEMINI_API_KEY or OPENAI_API_KEY must be set.
    """
    if LLM_PROVIDER == "openai":
        if not OPENAI_API_KEY:
            logger.error("LLM_PROVIDER is openai but OPENAI_API_KEY is not set")
            return None
        return openai_api_call(prompt)
    else:
        if not GEMINI_API_KEY:
            logger.error("LLM_PROVIDER is gemini but GEMINI_API_KEY is not set")
            return None
        return gemini_api_call(prompt)


# Summary Generation
def generate_summary_using_llm(title: str, transcript_text: str) -> Optional[str]:
    """
    Generate a summary of the transcript using the configured LLM.

    Args:
        title: Video title for context in the prompt.
        transcript_text: Full transcript text to summarize.

    Returns:
        Summary string (stripped, newlines replaced by spaces), or None on failure.
    """
    logger.info("Generating summary using LLM", extra={"title": title})

    prompt = get_summary_generation_prompt_template(title=title, transcript=transcript_text)

    try:
        result = llm_call(prompt)
        if result:
            result = result.strip().replace("\n", " ")
            logger.info("Successfully generated summary", extra={"summary_length": len(result)})
        return result
    except Exception as e:
        logger.error("Error generating AI summary", extra={"error": str(e)})
        return None


def is_valid_summary_length(summary: str) -> bool:
    """
    Check whether the summary length is within configured bounds.

    Args:
        summary: Summary text to validate.

    Returns:
        True if length is between MIN_SUMMARY_LENGTH and MAX_SUMMARY_LENGTH, False otherwise.
    """
    if not summary:
        return False
    length = len(summary)
    return MIN_SUMMARY_LENGTH <= length <= MAX_SUMMARY_LENGTH


def get_valid_ai_summary(title: Optional[str], transcript_text: str, attempts: int = 1) -> Optional[str]:
    """
    Generate an AI summary and retry until length is valid or max retries reached.

    Args:
        title: Video title for context (may be None).
        transcript_text: Full transcript text to summarize.
        attempts: Current attempt number (used internally for recursion).

    Returns:
        Summary string meeting length constraints, or the last generated summary if
        max retries reached, or None if generation failed.
    """
    logger.info(
        "Attempting to get valid AI summary",
        extra={"attempt": attempts, "max_tries": MAX_RETRIES},
    )

    ai_summary = generate_summary_using_llm(title, transcript_text)
    if ai_summary is None:
        return None

    if not is_valid_summary_length(ai_summary):
        if attempts < MAX_RETRIES:
            return get_valid_ai_summary(title, transcript_text, attempts + 1)
        else:
            logger.warning("Max retries reached, returning summary with invalid length")
            return ai_summary

    return ai_summary


# Update VidWiz API
def update_vidwiz_summary(video_id: str, ai_summary: str) -> bool:
    """
    Update the video summary in the VidWiz backend via POST.

    Args:
        video_id: Unique identifier for the video.
        ai_summary: Summary text to persist.

    Returns:
        True if the update succeeded (HTTP 200), False otherwise.
    """
    # Use api/v2/internal
    url = f"{VIDWIZ_ENDPOINT}/v2/internal/videos/{video_id}/summary"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {VIDWIZ_TOKEN}",
    }

    payload = {"summary": ai_summary}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            logger.info("Successfully updated summary", extra={"video_id": video_id})
            return True
        else:
            logger.error(
                "Failed to update summary", 
                extra={"video_id": video_id, "status": response.status_code, "error": response.text}
            )
            return False
    except Exception as e:
        logger.error("Error updating summary", extra={"video_id": video_id, "error": str(e)})
        return False


# Main Processor
def process_summary(video_id: str) -> None:
    """
    Run the full summary pipeline for one video.
    
    Steps:
    1. **Idempotency Check**: Fetches video details from API. If a summary already exists, skips redundancy.
    2. **Transcript Fetch**: Retrieves the video transcript from S3.
    3. **Generation**: Uses LLM to generate a summary.
    4. **Persistence**: Updates the video record in VidWiz via API.

    Args:
        video_id: Unique identifier for the video.

    Returns:
        None. Errors are logged; no exception is raised.
    """
    logger.info("Processing summary", extra={"video_id": video_id})

    try:
        # 1. Idempotency Check & Metadata Fetch
        # Renaming to video_details to avoid confusion with the inner 'metadata' field
        video_details = get_video_metadata(video_id)
        if not video_details:
            logger.error("Failed to fetch video details, cannot proceed", extra={"video_id": video_id})
            return

        # Ideally the API returns the "summary" field. If it does, we check it.
        if video_details.get("summary"):
            logger.info("Summary already exists for video, skipping generation", extra={"video_id": video_id})
            return

        title = video_details.get("title")

        # 2. Get transcript from S3
        transcript = get_transcript_from_s3(video_id)
        if not transcript:
            logger.error("Cannot process summary - transcript not available", extra={"video_id": video_id})
            return

        # Format transcript for LLM
        full_transcript_text = format_full_transcript(transcript)

        # Generate summary
        ai_summary = get_valid_ai_summary(title, full_transcript_text)

        if ai_summary:
            logger.info("Successfully generated AI summary", extra={"video_id": video_id})
            update_vidwiz_summary(video_id, ai_summary)
        else:
            logger.error("Failed to generate AI summary", extra={"video_id": video_id})

    except Exception as e:
        logger.error("Error processing summary", extra={"video_id": video_id, "error": str(e)})


# Lambda Entry Point
@logger.inject_lambda_context(log_event=True)
@event_parser(model=SummaryRequest, envelope=envelopes.SqsEnvelope)
def lambda_handler(event: List[SummaryRequest], context: LambdaContext) -> None:
    """
    Lambda handler to process summary generation requests from SQS.

    For each SummaryRequest in the batch: fetches transcript from S3, gets video metadata
    (title), generates a summary via the LLM, validates length, and updates the VidWiz API.

    Args:
        event: List of SummaryRequest (parsed from SQS envelope).
        context: Lambda execution context.

    Returns:
        None. Per-item failures are logged and processing continues for the rest.
    """
    logger.info("Starting summary processing", extra={"request_count": len(event)})

    for i, request in enumerate(event):
        logger.info(
            "Processing summary batch item",
            extra={"item_index": i + 1, "total_items": len(event), "video_id": request.video_id},
        )
        try:
            process_summary(request.video_id)
        except Exception as e:
            logger.error(
                "Failed to process summary", extra={"video_id": request.video_id, "error": str(e)}
            )
            continue

    logger.info("Completed summary processing batch", extra={"processed_count": len(event)})
