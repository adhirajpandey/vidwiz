# llm_note.py
# This script is a one-time utility designed to generate concise, AI-powered notes for YouTube videos based on their transcripts and user-provided timestamps. It is not actively maintained and was created to fulfill a specific use case.
# Features:
# - Connects to a PostgreSQL database to fetch notes that lack AI-generated content.
# - Retrieves YouTube video transcripts using the youtube_transcript_api.
# - Extracts relevant transcript segments based on provided timestamps.
# - Utilizes multiple(chosen) LLM providers (OpenAI, Gemini, OpenRouter) to generate concise, one-line notes in English, focusing on the transcript context.
# - Updates the database with the generated AI notes.
# - Handles configuration via environment variables and supports retry logic for note generation.
# Note:
# This script is not intended for long-term use or production deployment. It was written for a specific batch-processing task and is not actively maintained.

import json
from typing import Optional, List, Dict, Any
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import JSONFormatter
import psycopg2
import psycopg2.extras
import urllib.parse as urlparse
import os
import requests
from dotenv import load_dotenv
from vidwiz.shared.log import init_logging, get_logger

load_dotenv()
init_logging()
logger = get_logger("vidwiz.scripts.llm_note")

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
DATABASE_URL = os.getenv("DB_URL")


# Using mutliple LLM providers to bypass rate limits
def validate_config():
    """Validate that all required environment variables are set"""
    required_vars = {
        "Database URL": DATABASE_URL,
        "OpenAI API Key": OPENAI_API_KEY,
        "OpenAI Endpoint": OPENAI_ENDPOINT,
        "Gemini API Key": GEMINI_API_KEY,
        "Gemini Base URL": GEMINI_BASE_URL,
        "OpenRouter API Key": OPENROUTER_API_KEY,
        "OpenRouter Base URL": OPENROUTER_BASE_URL,
    }

    missing = [var for var, value in required_vars.items() if not value]
    if missing:
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )


def get_db_connection() -> Optional[psycopg2.extensions.connection]:
    """Get a database connection"""
    try:
        url = urlparse.urlparse(DATABASE_URL)
        db_params = {
            "dbname": url.path[1:],
            "user": url.username,
            "password": url.password,
            "host": url.hostname,
            "port": url.port,
        }
        return psycopg2.connect(**db_params)
    except Exception as e:
        logger.exception("Connection error")
        return None


def get_empty_notes() -> List[Dict[str, Any]]:
    """Get all notes that don't have AI notes"""
    conn = get_db_connection()
    if not conn:
        raise Exception("Database connection failed")
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                "SELECT * FROM ytnotes WHERE note IS NULL AND ai_note IS NULL"
            )
            return cursor.fetchall()
    except Exception as e:
        logger.exception("Error fetching empty notes")
        return []
    finally:
        conn.close()


def update_ai_note(note_id: int, ai_note: str) -> Optional[Dict[str, Any]]:
    """Update a note with AI-generated content"""
    conn = get_db_connection()
    if not conn:
        raise Exception("Database connection failed")
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(
                "UPDATE ytnotes SET ai_note = %s WHERE id = %s RETURNING *",
                (ai_note, note_id),
            )
            updated_note = cursor.fetchone()
            conn.commit()
            return updated_note
    except Exception as e:
        logger.exception("Error updating AI note")
        return None
    finally:
        conn.close()


def get_formatted_video_transcript(video_id: str) -> Optional[str]:
    """Get formatted transcript for a video"""
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id, ["en", "hi"])
        formatter = JSONFormatter()
        return (
            formatter.format_transcript(transcript)
            .encode("utf-8")
            .decode("unicode_escape")
        )
    except Exception as e:
        logger.exception("Error fetching transcript")
        return None


def format_timestamp_in_seconds(timestamp: str) -> int:
    """Convert timestamp to seconds"""
    parts = [int(x) for x in timestamp.split(":")]
    return sum(x * 60**i for i, x in enumerate(reversed(parts)))


def get_relevant_transcript(transcript: str, timestamp: str) -> Optional[str]:
    """Get relevant portion of transcript based on timestamp"""
    try:
        timestamp_in_seconds = format_timestamp_in_seconds(timestamp)
        transcript_data = json.loads(transcript)

        buffer = 15
        relevant = [
            seg
            for seg in transcript_data
            if (timestamp_in_seconds - buffer)
            <= seg["start"]
            <= (timestamp_in_seconds + buffer)
        ]
        if not relevant:
            return None

        closest_idx = min(
            range(len(transcript_data)),
            key=lambda i: abs(transcript_data[i]["start"] - timestamp_in_seconds),
        )

        before = transcript_data[max(0, closest_idx - 15) : closest_idx]
        after = transcript_data[closest_idx + 1 : closest_idx + 16]

        result = {
            "timestamp": transcript_data[closest_idx]["start"],
            "text": transcript_data[closest_idx]["text"],
            "before": before,
            "after": after,
        }
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        logger.exception("Error extracting relevant transcript")
        return None


def openai_api_call(prompt: str, model: str = "gpt-4o-mini") -> Optional[str]:
    """Send a prompt to OpenAI's model"""
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
    }

    try:
        resp = requests.post(OPENAI_ENDPOINT, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.exception("OpenAI API error")
        return None


def gemini_api_call(prompt: str, model: str = "gemini-2.0-flash") -> Optional[str]:
    """Send a prompt to Gemini API"""
    url = f"{GEMINI_BASE_URL}/models/{model}:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logger.exception("Gemini API error")
        return None


def openrouter_api_call(
    prompt: str, model: str = "google/gemini-2.0-flash-exp:free"
) -> Optional[str]:
    """Send a prompt to OpenRouter API"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
    }

    try:
        resp = requests.post(
            OPENROUTER_BASE_URL, headers=headers, json=payload, timeout=30
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.exception("OpenRouter API error")
        return None


def generate_note_using_llm(
    title: str,
    timestamp: str,
    note: Dict[str, Any],
    transcript: str,
    provider: str = "openai",
) -> Optional[str]:
    """Generate a note using the specified LLM provider"""
    prompt = f"""Generate a concise one-line note based on the provided title, timestamp, and transcript. 
    The note should be less than 120 characters and capture the essence of the content at the specified timestamp. 
    Focus more on the transcript context than the title. Do not include any additional text or formatting.
    
    Here are the details:
    Title: {title}
    Timestamp: {timestamp} - {format_timestamp_in_seconds(timestamp)} seconds
    Transcript: {transcript}

    Even if the transcript is in any language, generate a note in English.
    Return only the note, without any additional text or formatting.
    Do not add '\",\"',-,: any special character anywhere in the note.
    """

    try:
        match provider.lower():
            case "openai":
                return openai_api_call(prompt)
            case "gemini":
                return gemini_api_call(prompt)
            case "openrouter":
                return openrouter_api_call(prompt)
            case _:
                logger.error(
                    "Invalid provider: %s. Please choose from openai, gemini, or openrouter.",
                    provider,
                )
                return None
    except Exception as e:
        logger.exception("Error generating AI note")
        return None


def get_valid_ai_note(
    title: str,
    timestamp: str,
    note: Dict[str, Any],
    transcript: str,
    provider: str = "openai",
    tries: int = 1,
    max_tries: int = 3,
) -> Optional[str]:
    """Get a valid AI note with retries if needed"""
    ai_note = generate_note_using_llm(title, timestamp, note, transcript, provider)
    if ai_note is None:
        return None

    if len(ai_note) > 120 or len(ai_note) < 10:
        logger.info(
            "AI note for ID %s is too long or too short, retrying (attempt %d).",
            note.get("id"),
            tries,
        )
        if tries < max_tries:
            return get_valid_ai_note(
                title, timestamp, note, transcript, provider, tries + 1, max_tries
            )
        else:
            logger.warning("Max retries reached for note ID %s.", note.get("id"))
            return ai_note
    return ai_note


def main():
    validate_config()

    empty_notes = get_empty_notes()
    if not empty_notes:
        logger.info("No empty notes found.")
        return

    # Process notes by video to fetch transccript only once per video
    video_notes = {}
    for note in empty_notes:
        video_id = note.get("video_id")
        if video_id not in video_notes:
            video_notes[video_id] = []
        video_notes[video_id].append(note)

    for video_id, notes in video_notes.items():
        transcript = get_formatted_video_transcript(video_id)
        if not transcript:
            logger.info("No transcript found for video ID: %s", video_id)
            continue

        for note in notes:
            title = note.get("video_title")
            timestamp = note.get("note_timestamp")
            if not title or not timestamp:
                logger.warning(
                    "Note ID %s is missing title or timestamp.", note.get("id")
                )
                continue

            relevant_transcript = get_relevant_transcript(transcript, timestamp)
            if not relevant_transcript:
                logger.info(
                    "No relevant transcript found for note ID %s.", note.get("id")
                )
                continue

            ai_note = get_valid_ai_note(title, timestamp, note, relevant_transcript)
            logger.info("AI note for ID %s: %s", note.get("id"), ai_note)

            if ai_note:
                updated_note = update_ai_note(note.get("id"), ai_note)
                if updated_note:
                    logger.info(
                        "Updated note ID %s with AI note.", updated_note["id"]
                    )
                else:
                    logger.error(
                        "Failed to update note ID %s.", note.get("id")
                    )
            logger.info("-" * 50)


if __name__ == "__main__":
    main()
