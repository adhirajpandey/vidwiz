from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import BaseModel, envelopes, event_parser
from aws_lambda_powertools.utilities.typing import LambdaContext
from typing import Any, Dict, List, Optional
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

TRANSCRIPT_BUFFER_SECONDS = int(os.getenv("TRANSCRIPT_BUFFER_SECONDS", "15"))
CONTEXT_SEGMENTS = int(os.getenv("CONTEXT_SEGMENTS", "15"))
MAX_NOTE_LENGTH = int(os.getenv("MAX_NOTE_LENGTH", "120"))
MIN_NOTE_LENGTH = int(os.getenv("MIN_NOTE_LENGTH", "40"))
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
class Video(BaseModel):
    """
    Video model for transcript and metadata.

    Attributes:
        created_at: ISO timestamp when the video was created.
        id: Internal video ID.
        title: Video title.
        transcript_available: Whether a transcript exists.
        updated_at: ISO timestamp of last update.
        video_id: External video identifier (e.g. YouTube ID).
    """

    created_at: str
    id: int
    title: Optional[str] = None
    transcript_available: bool
    updated_at: str
    video_id: str


class Note(BaseModel):
    """
    Note model for processing requests (SQS payload).

    Attributes:
        created_at: ISO timestamp when the note was created (optional).
        generated_by_ai: Whether the note was AI-generated (optional).
        id: Internal note ID.
        text: Note content (optional).
        timestamp: Timestamp in video (e.g. HH:MM:SS).
        updated_at: ISO timestamp of last update (optional).
        user_id: Owner user ID.
        video: Nested Video model (optional).
        video_id: External video identifier.
    """

    created_at: Optional[str] = None
    generated_by_ai: Optional[bool] = None
    id: int
    text: Any = None
    timestamp: str
    updated_at: Optional[str] = None
    user_id: int
    video: Optional[Video] = None
    video_id: str


class TranscriptSegment(BaseModel):
    """
    A single transcript segment with offset and text.

    Attributes:
        offset: Time offset in seconds from the start of the video.
        text: Segment text.
    """

    offset: float
    text: str


class RelevantTranscriptContext(BaseModel):
    """
    Context around a target timestamp for note generation.

    Attributes:
        timestamp: Target timestamp in seconds.
        text: Main segment text at that timestamp.
        before: Segments immediately before the target.
        after: Segments immediately after the target.
    """

    timestamp: float
    text: str
    before: List[TranscriptSegment]
    after: List[TranscriptSegment]


# Utility Functions
def get_note_generation_prompt_template(
    max_length: int, title: Optional[str], timestamp: str, timestamp_seconds: int, transcript: str
) -> str:
    """
    Build the LLM prompt for generating a single note at a timestamp.

    Args:
        max_length: Maximum allowed note length in characters.
        title: Video title for context (optional; omitted from prompt if None).
        timestamp: Timestamp string (e.g. HH:MM:SS).
        timestamp_seconds: Same timestamp in seconds.
        transcript: Relevant transcript text around the timestamp.

    Returns:
        Filled-in prompt string for the LLM.
    """
    title_block = f"Title: {title}\n" if title else ""
    return f"""Generate a concise one-line note based on the provided title, timestamp, and transcript. 
The note should be less than {max_length} characters and capture the essence of the content at the specified timestamp. 
Focus more on the transcript context than the title. Do not include any additional text or formatting.

Here are the details:
{title_block}Timestamp: {timestamp} - {timestamp_seconds} seconds
Transcript: {transcript}

Even if the transcript is in any language, generate a note in English.
Return only the note, without any additional text or formatting.
Do not add '","",-,: any special character anywhere in the note.
"""


def format_timestamp_in_seconds(timestamp: str) -> int:
    """
    Convert timestamp to seconds.

    Args:
        timestamp: Time in HH:MM:SS format

    Returns:
        Time in seconds

    Raises:
        InvalidTimestampError: If timestamp format is invalid
    """
    logger.debug("Converting timestamp to seconds", extra={"timestamp": timestamp})

    try:
        parts = [int(x) for x in timestamp.split(":")]
        if len(parts) not in [2, 3]:  # MM:SS or HH:MM:SS
            raise Exception(f"Invalid timestamp format: {timestamp}")

        seconds = sum(x * 60**i for i, x in enumerate(reversed(parts)))
        logger.debug(
            "Successfully converted timestamp",
            extra={"timestamp": timestamp, "seconds": seconds},
        )
        return seconds

    except Exception as e:
        raise Exception(f"Invalid timestamp format: {timestamp}") from e


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
        logger.info(
            "Fetching transcript from S3",
            extra={
                "bucket": S3_BUCKET_NAME,
                "key": transcript_key,
                "video_id": video_id,
                "attempt": attempt,
            },
        )

        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=transcript_key)
        transcript_data = json.loads(response["Body"].read().decode("utf-8"))
        if transcript_data is None:
            logger.warning(
                "Transcript payload is null",
                extra={"video_id": video_id, "attempt": attempt},
            )
            return None
        if not isinstance(transcript_data, list):
            logger.warning(
                "Transcript payload is not a list",
                extra={"video_id": video_id, "attempt": attempt, "payload_type": type(transcript_data).__name__},
            )
            return None

        logger.info(
            "Successfully loaded transcript from S3",
            extra={"video_id": video_id, "segment_count": len(transcript_data), "attempt": attempt},
        )
        return transcript_data

    except Exception as e:
        logger.warning(
            "Failed to get transcript from S3",
            extra={
                "video_id": video_id,
                "attempt": attempt,
                "max_retries": TRANSCRIPT_FETCH_MAX_RETRIES,
                "error": str(e),
            },
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


def get_relevant_transcript(
    transcript: List[Dict], timestamp: str
) -> Optional[RelevantTranscriptContext]:
    """
    Get relevant portion of transcript based on timestamp with context.

    Args:
        transcript: List of transcript segments with 'offset' and 'text' fields
        timestamp: Target timestamp in HH:MM:SS format

    Returns:
        RelevantTranscriptContext with context or None if not found

    Raises:
        InvalidTimestampError: If timestamp format is invalid
    """
    logger.info("Getting relevant transcript", extra={"timestamp": timestamp})

    try:
        timestamp_in_seconds = format_timestamp_in_seconds(timestamp)

        # Find segments within buffer range
        relevant = [
            seg
            for seg in transcript
            if (timestamp_in_seconds - TRANSCRIPT_BUFFER_SECONDS)
            <= float(seg["offset"])
            <= (timestamp_in_seconds + TRANSCRIPT_BUFFER_SECONDS)
        ]

        if not relevant:
            logger.warning(
                "No relevant segments found within buffer range",
                extra={
                    "timestamp_in_seconds": timestamp_in_seconds,
                    "buffer": TRANSCRIPT_BUFFER_SECONDS,
                },
            )
            return None

        # Find the closest segment to the target timestamp
        closest_idx = min(
            range(len(transcript)),
            key=lambda i: abs(float(transcript[i]["offset"]) - timestamp_in_seconds),
        )

        # Get context segments before and after the target
        start_idx = max(0, closest_idx - CONTEXT_SEGMENTS)
        end_idx = closest_idx + CONTEXT_SEGMENTS + 1

        before_segments = [
            TranscriptSegment(offset=float(seg["offset"]), text=seg["text"])
            for seg in transcript[start_idx:closest_idx]
        ]
        after_segments = [
            TranscriptSegment(offset=float(seg["offset"]), text=seg["text"])
            for seg in transcript[closest_idx + 1 : end_idx]
        ]

        result = RelevantTranscriptContext(
            timestamp=float(transcript[closest_idx]["offset"]),
            text=transcript[closest_idx]["text"],
            before=before_segments,
            after=after_segments,
        )

        logger.debug(
            "Successfully extracted relevant transcript",
            extra={
                "closest_timestamp": result.timestamp,
                "context_before_count": len(before_segments),
                "context_after_count": len(after_segments),
            },
        )
        return result

    except Exception as e:
        logger.error(
            "Error extracting relevant transcript",
            extra={"error": str(e), "timestamp": timestamp},
        )
        raise Exception("Failed to extract relevant transcript") from e


def format_transcript_context(context: RelevantTranscriptContext) -> str:
    """
    Format transcript context into a readable string.

    Args:
        context: RelevantTranscriptContext object

    Returns:
        Formatted transcript string
    """
    parts = []

    # Add before context
    if context.before:
        before_text = " ".join([seg.text for seg in context.before])
        parts.append(before_text)

    # Add main text
    parts.append(f"[{context.text}]")  # Mark the main segment

    # Add after context
    if context.after:
        after_text = " ".join([seg.text for seg in context.after])
        parts.append(after_text)

    return " ".join(parts)


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
    Sends a text prompt to the OpenAI Responses API using the gpt-5-nano model
    and returns the generated text.

    Args:
        prompt (str): The prompt / instruction to send to the model.

    Returns:
        str: The model’s text output.
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


def generate_note_using_llm(
    title: Optional[str], timestamp: str, transcript_context: RelevantTranscriptContext
) -> Optional[str]:
    """
    Generate a note using LLM based on video content.

    Args:
        title: Video title for context (optional; omitted from prompt if None).
        timestamp: Specific timestamp in the video
        transcript_context: RelevantTranscriptContext object with transcript data

    Returns:
        Generated note text or None if failed
    """
    logger.info(
        "Generating note using LLM", extra={"title": title or "N/A", "timestamp": timestamp}
    )

    # Format the transcript context
    formatted_transcript = format_transcript_context(transcript_context)

    # Get the prompt with parameters filled in
    prompt = get_note_generation_prompt_template(
        max_length=MAX_NOTE_LENGTH,
        title=title,
        timestamp=timestamp,
        timestamp_seconds=format_timestamp_in_seconds(timestamp),
        transcript=formatted_transcript,
    )

    try:
        result = llm_call(prompt)

        if result:
            # Clean up the result - remove extra whitespace and newlines
            result = result.strip().replace("\n", " ")
            logger.info(
                "Successfully generated note using LLM",
                extra={"note_length": len(result)},
            )
        return result
    except Exception as e:
        logger.error("Error generating AI note", extra={"error": str(e)})
        return None


def is_valid_note_length(note: str) -> bool:
    """
    Check if note meets length requirements.

    Args:
        note: Note text to validate

    Returns:
        True if note length is valid, False otherwise
    """
    if not note:
        return False

    note_length = len(note)
    return MIN_NOTE_LENGTH <= note_length <= MAX_NOTE_LENGTH


def get_valid_ai_note(
    title: Optional[str],
    timestamp: str,
    transcript_context: RelevantTranscriptContext,
    attempts: int = 1,
) -> Optional[str]:
    """
    Get a valid AI note with retries if length requirements aren't met.

    Args:
        title: Video title for context (optional; omitted from prompt if None).
        timestamp: Specific timestamp in the video
        transcript_context: RelevantTranscriptContext object
        attempts: Current attempt number

    Returns:
        Valid AI note text or None if all attempts failed
    """
    logger.info(
        "Attempting to get valid AI note",
        extra={"attempt": attempts, "max_tries": MAX_RETRIES},
    )

    ai_note = generate_note_using_llm(title, timestamp, transcript_context)
    if ai_note is None:
        logger.warning("Failed to generate AI note")
        return None

    if not is_valid_note_length(ai_note):
        logger.warning(
            "AI note length invalid, retrying",
            extra={
                "note_length": len(ai_note),
                "attempt": attempts,
                "max_tries": MAX_RETRIES,
                "min_length": MIN_NOTE_LENGTH,
                "max_length": MAX_NOTE_LENGTH,
            },
        )
        if attempts < MAX_RETRIES:
            return get_valid_ai_note(title, timestamp, transcript_context, attempts + 1)
        else:
            logger.warning(
                "Max retries reached, returning note with invalid length",
                extra={"note_length": len(ai_note)},
            )
            return ai_note

    logger.info("Generated valid AI note", extra={"note_length": len(ai_note)})
    return ai_note


def update_vidwiz_note(note_id: str, ai_note: str) -> bool:
    """
    Update a note in the VidWiz backend with AI-generated text via PATCH.

    Args:
        note_id: Internal note ID to update.
        ai_note: Generated note text to persist.

    Returns:
        True if the update succeeded (HTTP 200), False otherwise.
    """
    # Use api/v2/internal
    url = f"{VIDWIZ_ENDPOINT}/v2/internal/notes/{note_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {VIDWIZ_TOKEN}",
    }
    payload = {"text": ai_note, "generated_by_ai": True}

    try:
        response = requests.patch(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            logger.info("Successfully updated note", extra={"note_id": note_id})
            return True
        logger.error(
            "Failed to update note",
            extra={"note_id": note_id, "status": response.status_code, "error": response.text},
        )
        return False
    except Exception as e:
        logger.error("Error updating note", extra={"note_id": note_id, "error": str(e)})
        return False


def process_note(note: Note) -> None:
    """
    Process a single note by generating AI content from transcript and updating VidWiz.

    Fetches transcript from S3, extracts relevant context at the note timestamp,
    generates an AI note via the LLM, validates length, and PATCHes the note in VidWiz.

    Robustness:
    - Handles missing nested `video` object by falling back to API metadata fetch for title.
    - Acccepts minimal note payloads (id, video_id, timestamp).

    Args:
        note: Note object containing video and timestamp information.

    Returns:
        None. Errors are logged; no exception is raised.
    """
    logger.info(
        "Processing note", extra={"note_id": note.id, "video_id": note.video_id}
    )

    try:
        # Get transcript from S3 cache
        transcript = get_transcript_from_s3(note.video_id)
        if not transcript:
            logger.error(
                "Cannot process note - transcript not available",
                extra={"video_id": note.video_id, "note_id": note.id},
            )
            return

        # Extract relevant portion of transcript based on timestamp
        relevant_transcript = get_relevant_transcript(transcript, note.timestamp)
        if relevant_transcript is None:
            logger.error(
                "Cannot process note - relevant transcript not found",
                extra={
                    "video_id": note.video_id,
                    "note_id": note.id,
                    "timestamp": note.timestamp,
                },
            )
            return

        # Resolve title: use video.title if available, else metadata['title']; if neither, pass None (omit from LLM prompt)
        title = None
        if note.video and note.video.title:
            title = note.video.title
        else:
            metadata = get_video_metadata(note.video_id)
            title = metadata.get("title") if metadata else None

        # Generate AI note from the relevant transcript
        ai_note = get_valid_ai_note(
            title, note.timestamp, relevant_transcript
        )

        if ai_note:
            logger.info(
                "Successfully generated AI note",
                extra={"note_id": note.id, "ai_note": ai_note},
            )
            # Update the note in VidWiz
            update_vidwiz_note(note.id, ai_note)
        else:
            logger.error("Failed to generate AI note", extra={"note_id": note.id})

    except Exception as e:
        logger.error(
            "Error processing note", extra={"note_id": note.id, "error": str(e)}
        )


# Lambda Entry Point
@logger.inject_lambda_context(log_event=True)
@event_parser(model=Note, envelope=envelopes.SqsEnvelope)
def lambda_handler(event: List[Note], context: LambdaContext) -> None:
    """
    Lambda handler to process note generation requests from SQS.

    For each Note in the batch: fetches transcript from S3, extracts relevant
    transcript at the note timestamp, generates an AI note via the LLM, validates
    length, and updates the note in the VidWiz API.

    Args:
        event: List of Note objects from SQS messages (parsed from SQS envelope).
        context: Lambda execution context.

    Returns:
        None. Per-note failures are logged and processing continues for the rest.
    """
    logger.info("Starting note processing", extra={"note_count": len(event)})

    for i, note in enumerate(event):
        logger.info(
            "Processing note batch item",
            extra={"item_index": i + 1, "total_items": len(event), "note_id": note.id},
        )
        try:
            process_note(note)
        except Exception as e:
            logger.error(
                "Failed to process note", extra={"note_id": note.id, "error": str(e)}
            )
            continue

    logger.info(
        "Completed note processing batch", extra={"processed_count": len(event)}
    )
