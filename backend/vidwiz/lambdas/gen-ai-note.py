from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import BaseModel, envelopes, event_parser
from aws_lambda_powertools.utilities.typing import LambdaContext
from typing import Any, Dict, List, Optional
import json
import os
import boto3
import requests

# Configuration constants
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")
VIDWIZ_ENDPOINT = os.getenv("VIDWIZ_ENDPOINT")
VIDWIZ_TOKEN = os.getenv("VIDWIZ_TOKEN")

assert GEMINI_API_KEY, "GEMINI_API_KEY is not set"
assert S3_BUCKET_NAME, "S3_BUCKET_NAME is not set"
assert VIDWIZ_ENDPOINT, "VIDWIZ_ENDPOINT is not set"
assert VIDWIZ_TOKEN, "VIDWIZ_TOKEN is not set"

TRANSCRIPT_BUFFER_SECONDS = int(os.getenv("TRANSCRIPT_BUFFER_SECONDS", "15"))
CONTEXT_SEGMENTS = int(os.getenv("CONTEXT_SEGMENTS", "15"))
MAX_NOTE_LENGTH = int(os.getenv("MAX_NOTE_LENGTH", "120"))
MIN_NOTE_LENGTH = int(os.getenv("MIN_NOTE_LENGTH", "40"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))


# Initialize logger
logger = Logger()


# Data Models
class Video(BaseModel):
    """Video model for transcript data."""

    created_at: str
    id: int
    title: str
    transcript_available: bool
    updated_at: str
    video_id: str


class Note(BaseModel):
    """Note model for processing requests."""

    created_at: str
    generated_by_ai: bool
    id: int
    text: Any
    timestamp: str
    updated_at: str
    user_id: int
    video: Video
    video_id: str


class TranscriptSegment(BaseModel):
    """Represents a single transcript segment."""

    offset: float
    text: str


class RelevantTranscriptContext(BaseModel):
    """Contains relevant transcript context for note generation."""

    timestamp: float
    text: str
    before: List[TranscriptSegment]
    after: List[TranscriptSegment]


# Utility Functions
def get_note_generation_prompt_template(
    max_length: int, title: str, timestamp: str, timestamp_seconds: int, transcript: str
) -> str:
    """Get the note generation prompt with parameters filled in."""
    return f"""Generate a concise one-line note based on the provided title, timestamp, and transcript. 
The note should be less than {max_length} characters and capture the essence of the content at the specified timestamp. 
Focus more on the transcript context than the title. Do not include any additional text or formatting.

Here are the details:
Title: {title}
Timestamp: {timestamp} - {timestamp_seconds} seconds
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
    """Get initialized S3 client."""
    return boto3.client("s3")


def get_transcript_from_s3(video_id: str) -> Optional[List[Dict]]:
    """
    Get transcript from S3 cache.

    Args:
        video_id: Unique identifier for the video

    Returns:
        List of transcript segments or None if not found

    Raises:
        TranscriptNotFoundError: If transcript cannot be retrieved
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
            },
        )

        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=transcript_key)
        transcript_data = json.loads(response["Body"].read().decode("utf-8"))

        logger.info(
            "Successfully loaded transcript from S3",
            extra={"video_id": video_id, "segment_count": len(transcript_data)},
        )
        return transcript_data

    except Exception as e:
        logger.warning(
            "Transcript not found in S3", extra={"video_id": video_id, "error": str(e)}
        )
        raise Exception(f"Transcript not found for video {video_id}") from e


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


# AI/LLM Functions
def gemini_api_call(prompt: str) -> Optional[str]:
    """
    Make API call to Gemini AI model.

    Args:
        prompt: Text prompt to send to the Gemini API

    Returns:
        Generated text response or None if the request failed
    """
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


def generate_note_using_llm(
    title: str, timestamp: str, transcript_context: RelevantTranscriptContext
) -> Optional[str]:
    """
    Generate a note using LLM based on video content.

    Args:
        title: Video title for context
        timestamp: Specific timestamp in the video
        transcript_context: RelevantTranscriptContext object with transcript data

    Returns:
        Generated note text or None if failed
    """
    logger.info(
        "Generating note using LLM", extra={"title": title, "timestamp": timestamp}
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
        result = gemini_api_call(prompt)
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
    title: str,
    timestamp: str,
    transcript_context: RelevantTranscriptContext,
    attempts: int = 1,
) -> Optional[str]:
    """
    Get a valid AI note with retries if length requirements aren't met.

    Args:
        title: Video title for context
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


def update_vidwiz_note(note_id: str, ai_note: str):
    url = f"{VIDWIZ_ENDPOINT}/notes/{note_id}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {VIDWIZ_TOKEN}",
    }
    payload = {"text": ai_note, "generated_by_ai": True}

    response = requests.patch(url, json=payload, headers=headers)
    if response.status_code == 200:
        logger.info("Successfully updated note", extra={"note_id": note_id})
    else:
        logger.error(
            "Failed to update note", extra={"note_id": note_id, "error": response.text}
        )


def process_note(note: Note) -> None:
    """
    Process a single note by generating AI content from transcript.

    Args:
        note: Note object containing video and timestamp information
    """
    logger.info(
        "Processing note", extra={"note_id": note.id, "video_id": note.video_id}
    )

    try:
        # Get transcript from S3 cache
        transcript = get_transcript_from_s3(note.video_id)
        if transcript is None:
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

        # Generate AI note from the relevant transcript
        ai_note = get_valid_ai_note(
            note.video.title, note.timestamp, relevant_transcript
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

    This function processes batches of notes by:
    1. Fetching video transcripts from S3
    2. Extracting relevant transcript segments based on timestamps
    3. Generating AI-powered notes using the Gemini LLM
    4. Validating note length and quality
    5. Updating the notes back to VidWiz API

    Args:
        event: List of Note objects from SQS messages
        context: Lambda execution context
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
