import json
import os
import requests
from typing import Dict, Any, Optional, List
import boto3
from vidwiz.logging_config import get_logger, configure_logging

# Ensure logging configured in lambda context
configure_logging()
logger = get_logger("vidwiz.lambda.gen_note")


# Environment variables
logger.info("Loading environment variables...")
BASE_URL = os.getenv("BASE_URL")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")
PREFERRED_PROVIDER = os.getenv("PREFERRED_PROVIDER", "gemini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "vidwiz")
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
logger.info(f"Environment loaded. Preferred provider: {PREFERRED_PROVIDER}")

s3_client = boto3.client("s3")


def check_authorization(headers: Dict[str, str]) -> bool:
    """Check if the request is authorized using Bearer token"""
    logger.debug("Checking authorization...")
    try:
        auth_header = headers.get("authorization", "")
        logger.debug(f"Auth header present: {bool(auth_header)}")
        if not auth_header.startswith("Bearer "):
            logger.warning("Invalid auth header format")
            return False

        token = auth_header.split(" ")[1]
        is_valid = token == AUTH_TOKEN
        logger.debug(f"Token validation result: {is_valid}")
        return is_valid
    except Exception as e:
        logger.exception(f"Authorization error: {e}")
        return False


def get_transcript_from_s3(video_id: str) -> Optional[List[Dict]]:
    """Get transcript from S3 cache."""
    if not S3_BUCKET_NAME:
        return None

    transcript_key = f"transcripts/{video_id}.json"
    try:
        logger.info(
            f"Checking for transcript in S3: s3://{S3_BUCKET_NAME}/{transcript_key}"
        )
        response = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=transcript_key)
        transcript_data = json.loads(response["Body"].read().decode("utf-8"))
        logger.info(f"Successfully loaded transcript from S3 for video ID: {video_id}")
        return transcript_data
    except Exception as e:
        logger.info(
            f"Transcript not found in S3 for video ID: {video_id} (error: {e}). Fetching from API."
        )
        return None


def get_transcript_from_api(video_id: str) -> Optional[List[Dict]]:
    """Get transcript from RapidAPI."""
    logger.info(f"Fetching transcript for video ID: {video_id} from RapidAPI")
    api_url = "https://youtube-transcript3.p.rapidapi.com/api/transcript"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "youtube-transcript3.p.rapidapi.com",
    }

    try:
        url = f"{api_url}?videoId={video_id}"
        response = requests.get(url, headers=headers, timeout=10)
        logger.debug(f"Transcript API response status: {response.status_code}")
        response.raise_for_status()
        response_data = response.json()

        if "error" in response_data or not response_data.get("success"):
            logger.warning(
                f"API returned an error or unsuccessful response: {response_data.get('error')}"
            )
            return None

        transcript = response_data.get("transcript", [])
        logger.info(
            f"Successfully retrieved transcript with {len(transcript)} segments from API"
        )
        return transcript
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching transcript from RapidAPI: {e}")
        return None


def store_transcript_in_s3(video_id: str, transcript: List[Dict]):
    """Store transcript in S3."""
    if not S3_BUCKET_NAME or not transcript:
        return

    transcript_key = f"transcripts/{video_id}.json"
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=transcript_key,
            Body=json.dumps(transcript),
            ContentType="application/json",
        )
        logger.info(
            f"Successfully stored transcript in S3: s3://{S3_BUCKET_NAME}/{transcript_key}"
        )
    except Exception as e:
        logger.error(f"Error storing transcript in S3: {e}")


def get_transcript(video_id: str):
    """
    Get transcript for a video, trying S3 cache first,
    then falling back to API.
    """
    transcript = get_transcript_from_s3(video_id)
    if transcript is not None:
        return transcript

    transcript = get_transcript_from_api(video_id)
    if transcript is not None:
        store_transcript_in_s3(video_id, transcript)
        return transcript

    return None


def format_timestamp_in_seconds(timestamp: str) -> int:
    """Convert timestamp to seconds"""
    logger.debug(f"Converting timestamp to seconds: {timestamp}")
    parts = [int(x) for x in timestamp.split(":")]
    seconds = sum(x * 60**i for i, x in enumerate(reversed(parts)))
    logger.debug(f"Converted to {seconds} seconds")
    return seconds


def get_relevant_transcript(transcript: List[Dict], timestamp: str) -> Optional[str]:
    """Get relevant portion of transcript based on timestamp"""
    logger.info(f"Getting relevant transcript for timestamp: {timestamp}")
    try:
        if not transcript:
            logger.warning("No transcript provided")
            return None

        timestamp_in_seconds = format_timestamp_in_seconds(timestamp)
        logger.debug(f"Looking for content around {timestamp_in_seconds} seconds")

        buffer = 15
        relevant = [
            seg
            for seg in transcript
            if (timestamp_in_seconds - buffer)
            <= float(seg["offset"])
            <= (timestamp_in_seconds + buffer)
        ]
        if not relevant:
            logger.info("No relevant segments found within buffer range")
            return None

        closest_idx = min(
            range(len(transcript)),
            key=lambda i: abs(float(transcript[i]["offset"]) - timestamp_in_seconds),
        )
        logger.debug(f"Found closest segment at index {closest_idx}")

        before = transcript[max(0, closest_idx - 15) : closest_idx]
        after = transcript[closest_idx + 1 : closest_idx + 16]

        result = {
            "timestamp": float(transcript[closest_idx]["offset"]),
            "text": transcript[closest_idx]["text"],
            "before": before,
            "after": after,
        }
        logger.info(
            f"Extracted relevant transcript with {len(before)} segments before and {len(after)} segments after"
        )
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.exception(f"Error extracting relevant transcript: {e}")
        return None


def openai_api_call(prompt: str) -> Optional[str]:
    """Make API call to OpenAI"""
    logger.info("Making OpenAI API call...")
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
    }
    logger.debug(f"Payload: {payload}")
    try:
        response = requests.post(
            OPENAI_ENDPOINT, json=payload, headers=headers, timeout=10
        )
        logger.debug(f"Response status code: {response.status_code}")
        response.raise_for_status()
        response_data = response.json()
        logger.debug(f"OpenAI response: {response_data}")
        if "error" in response_data:
            logger.error(f"OpenAI API error: {response_data['error']}")
            return None
        result = response_data["choices"][0]["message"]["content"]
        logger.info("Successfully received response from OpenAI")
        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"OpenAI API error: {e}")
        return None


def gemini_api_call(prompt: str) -> Optional[str]:
    """Make API call to Gemini"""
    logger.info("Making Gemini API call...")
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(
            GEMINI_ENDPOINT, json=payload, headers=headers, timeout=10
        )
        response.raise_for_status()
        response_data = response.json()
        if "error" in response_data:
            logger.error(f"Gemini API error: {response_data['error']}")
            return None
        result = response_data["candidates"][0]["content"]["parts"][0]["text"]
        logger.info("Successfully received response from Gemini")
        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"Gemini API error: {e}")
        return None


def generate_note_using_llm(
    title: str, timestamp: str, note: Dict[str, Any], transcript: str
) -> Optional[str]:
    """Generate a note using LLM"""
    logger.info(f"Generating note for video: {title} at timestamp: {timestamp}")
    prompt = f"""Generate a concise one-line note based on the provided title, timestamp, and transcript. 
    The note should be less than 120 characters and capture the essence of the content at the specified timestamp. 
    Focus more on the transcript context than the title. Do not include any additional text or formatting.
    
    Here are the details:
    Title: {title}
    Timestamp: {timestamp} - {format_timestamp_in_seconds(timestamp)} seconds
    Transcript: {transcript}

    Even if the transcript is in any language, generate a note in English.
    Return only the note, without any additional text or formatting.
    Do not add '","",-,: any special character anywhere in the note.
    """

    try:
        if PREFERRED_PROVIDER == "gemini" and GEMINI_API_KEY:
            logger.info("Using Gemini provider")
            return gemini_api_call(prompt)
        elif PREFERRED_PROVIDER == "openai" and OPENAI_API_KEY:
            logger.info("Using OpenAI provider")
            return openai_api_call(prompt)
        else:
            logger.error("No valid API key found for the preferred provider")
            return None
    except Exception as e:
        logger.exception(f"Error generating AI note: {e}")
        return None


def get_valid_ai_note(
    title: str,
    timestamp: str,
    note: Dict[str, Any],
    transcript: str,
    tries: int = 1,
    max_tries: int = 3,
) -> Optional[str]:
    """Get a valid AI note with retries if needed"""
    logger.info(f"Attempting to get valid AI note (attempt {tries}/{max_tries})")
    ai_note = generate_note_using_llm(title, timestamp, note, transcript)
    if ai_note is None:
        logger.warning("Failed to generate AI note")
        return None

    if len(ai_note) > 120 or len(ai_note) < 10:
        logger.info(
            f"AI note length invalid ({len(ai_note)} chars). Retrying (attempt {tries}/{max_tries})"
        )
        if tries < max_tries:
            return get_valid_ai_note(
                title, timestamp, note, transcript, tries + 1, max_tries
            )
        else:
            logger.warning(f"Max retries reached for note ID {note.get('id')}")
            return ai_note
    logger.info(f"Generated valid AI note with length {len(ai_note)}")
    return ai_note


def lambda_handler(event, context):
    """AWS Lambda handler function"""
    logger.info("Lambda function started")
    logger.debug(f"Event received: {json.dumps(event)}")
    try:
        # Check authorization
        headers = event.get("headers", {})
        if not check_authorization(headers):
            logger.warning("Authorization failed")
            return {"statusCode": 401, "body": json.dumps({"error": "Unauthorized"})}

        # Get note data from the event
        note_data = event.get("body", {})
        if isinstance(note_data, str):
            note_data = json.loads(note_data)
        logger.debug(f"Note data: {json.dumps(note_data)}")

        if not note_data:
            logger.warning("No data provided in request")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "No data provided"}),
            }

        # Extract required fields
        note_id = note_data.get("id")
        video_id = note_data.get("video_id")
        video_title = note_data.get("video_title")
        note_timestamp = note_data.get("note_timestamp")
        logger.info(
            f"Extracted fields - Note ID: {note_id}, Video ID: {video_id}, Timestamp: {note_timestamp}"
        )

        if not all([note_id, video_id, video_title, note_timestamp]):
            logger.warning("Missing required fields")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing required fields"}),
            }

        # Get transcript
        transcript = get_transcript(video_id)
        if not transcript:
            logger.warning("Transcript not found")
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Transcript not found"}),
            }

        # Get relevant transcript portion
        relevant_transcript = get_relevant_transcript(transcript, note_timestamp)
        if not relevant_transcript:
            logger.info("No relevant transcript found")
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "No relevant transcript found"}),
            }

        # Generate AI note
        ai_note = get_valid_ai_note(
            video_title, note_timestamp, note_data, relevant_transcript
        )
        if not ai_note:
            logger.error("Failed to generate AI note")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Failed to generate AI note"}),
            }

        # Update note with AI note using PATCH request
        update_url = f"{BASE_URL}/notes/{note_id}"
        logger.info(f"Updating note at URL: {update_url}")
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {AUTH_TOKEN}",
            }
            response = requests.patch(
                update_url,
                headers=headers,
                json={"text": ai_note, "generated_by_ai": True},
                timeout=10,
            )
            response.raise_for_status()
            update_response = response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to update note: {e}")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"Failed to update note: {str(e)}"}),
            }

        logger.info("Successfully completed note generation and update")
        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Successfully generated and updated AI note",
                    "note": update_response,
                }
            ),
        }

    except Exception as e:
        logger.exception(f"Unexpected error in lambda handler: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
