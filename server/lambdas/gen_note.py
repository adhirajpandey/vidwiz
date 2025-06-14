import json
import os
import requests
from typing import Dict, Any, Optional, List


# Environment variables
print("Loading environment variables...")
BASE_URL = os.getenv("BASE_URL")
AUTH_TOKEN = os.getenv("AUTH_TOKEN")
PREFERRED_PROVIDER = os.getenv("PREFERRED_PROVIDER", "gemini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
OPENAI_ENDPOINT = "https://api.openai.com/v1/chat/completions"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
print(f"Environment loaded. Preferred provider: {PREFERRED_PROVIDER}")


def check_authorization(headers: Dict[str, str]) -> bool:
    """Check if the request is authorized using Bearer token"""
    print("Checking authorization...")
    try:
        auth_header = headers.get("authorization", "")
        print(f"Auth header present: {bool(auth_header)}")
        if not auth_header.startswith("Bearer "):
            print("Invalid auth header format")
            return False

        token = auth_header.split(" ")[1]
        is_valid = token == AUTH_TOKEN
        print(f"Token validation result: {is_valid}")
        return is_valid
    except Exception as e:
        print(f"Authorization error: {e}")
        return False


def get_transcript(video_id: str):
    """Get transcript for a video using RapidAPI"""
    print(f"Fetching transcript for video ID: {video_id}")
    url = "https://youtube-transcript3.p.rapidapi.com/api/transcript"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "youtube-transcript3.p.rapidapi.com",
    }

    try:
        url = f"{url}?videoId={video_id}"
        response = requests.get(url, headers=headers, timeout=120)
        response.raise_for_status()
        response_data = response.json()
        print(response_data)
        if "error" in response_data:
            print(f"API returned error: {response_data['error']}")
            return None
        if not response_data.get("success"):
            print("API returned unsuccessful response")
            return None
        transcript = response_data.get("transcript", [])
        print(f"Successfully retrieved transcript with {len(transcript)} segments")
        return transcript
    except requests.exceptions.RequestException as e:
        print(f"Error fetching transcript: {e}")
        return None


def format_timestamp_in_seconds(timestamp: str) -> int:
    """Convert timestamp to seconds"""
    print(f"Converting timestamp to seconds: {timestamp}")
    parts = [int(x) for x in timestamp.split(":")]
    seconds = sum(x * 60**i for i, x in enumerate(reversed(parts)))
    print(f"Converted to {seconds} seconds")
    return seconds


def get_relevant_transcript(transcript: List[Dict], timestamp: str) -> Optional[str]:
    """Get relevant portion of transcript based on timestamp"""
    print(f"Getting relevant transcript for timestamp: {timestamp}")
    try:
        if not transcript:
            print("No transcript provided")
            return None

        timestamp_in_seconds = format_timestamp_in_seconds(timestamp)
        print(f"Looking for content around {timestamp_in_seconds} seconds")

        buffer = 15
        relevant = [
            seg
            for seg in transcript
            if (timestamp_in_seconds - buffer)
            <= float(seg["offset"])
            <= (timestamp_in_seconds + buffer)
        ]
        if not relevant:
            print("No relevant segments found within buffer range")
            return None

        closest_idx = min(
            range(len(transcript)),
            key=lambda i: abs(float(transcript[i]["offset"]) - timestamp_in_seconds),
        )
        print(f"Found closest segment at index {closest_idx}")

        before = transcript[max(0, closest_idx - 15) : closest_idx]
        after = transcript[closest_idx + 1 : closest_idx + 16]

        result = {
            "timestamp": float(transcript[closest_idx]["offset"]),
            "text": transcript[closest_idx]["text"],
            "before": before,
            "after": after,
        }
        print(
            f"Extracted relevant transcript with {len(before)} segments before and {len(after)} segments after"
        )
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        print(f"Error extracting relevant transcript: {e}")
        return None


def openai_api_call(prompt: str) -> Optional[str]:
    """Make API call to OpenAI"""
    print("Making OpenAI API call...")
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

    try:
        response = requests.post(
            OPENAI_ENDPOINT, json=payload, headers=headers, timeout=120
        )
        response.raise_for_status()
        response_data = response.json()
        if "error" in response_data:
            print(f"OpenAI API error: {response_data['error']}")
            return None
        result = response_data["choices"][0]["message"]["content"]
        print("Successfully received response from OpenAI")
        return result
    except requests.exceptions.RequestException as e:
        print(f"OpenAI API error: {e}")
        return None


def gemini_api_call(prompt: str) -> Optional[str]:
    """Make API call to Gemini"""
    print("Making Gemini API call...")
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY}
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = requests.post(
            GEMINI_ENDPOINT, json=payload, headers=headers, timeout=120
        )
        response.raise_for_status()
        response_data = response.json()
        if "error" in response_data:
            print(f"Gemini API error: {response_data['error']}")
            return None
        result = response_data["candidates"][0]["content"]["parts"][0]["text"]
        print("Successfully received response from Gemini")
        return result
    except requests.exceptions.RequestException as e:
        print(f"Gemini API error: {e}")
        return None


def generate_note_using_llm(
    title: str, timestamp: str, note: Dict[str, Any], transcript: str
) -> Optional[str]:
    """Generate a note using LLM"""
    print(f"Generating note for video: {title} at timestamp: {timestamp}")
    prompt = f"""Generate a concise one-line note based on the provided title, timestamp, and transcript. 
    The note should be less than 120 characters and capture the essence of the content at the specified timestamp. 
    Focus more on the transcript context than the title. Do not include any additional text or formatting.
    
    Here are the details:
    Title: {title}
    Timestamp: {timestamp} - {format_timestamp_in_seconds(timestamp)} seconds
    Transcript: {transcript}

    Even if the transcript is in any language, generate a note in English.
    Return only the note, without any additional text or formatting.
    Do not add ',"",-,: any special character anywhere in the note.
    """

    try:
        if PREFERRED_PROVIDER == "gemini" and GEMINI_API_KEY:
            print("Using Gemini provider")
            return gemini_api_call(prompt)
        elif PREFERRED_PROVIDER == "openai" and OPENAI_API_KEY:
            print("Using OpenAI provider")
            return openai_api_call(prompt)
        else:
            print("No valid API key found for the preferred provider")
            return None
    except Exception as e:
        print(f"Error generating AI note: {e}")
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
    print(f"Attempting to get valid AI note (attempt {tries}/{max_tries})")
    ai_note = generate_note_using_llm(title, timestamp, note, transcript)
    if ai_note is None:
        print("Failed to generate AI note")
        return None

    if len(ai_note) > 120 or len(ai_note) < 10:
        print(
            f"AI note length invalid ({len(ai_note)} chars). Retrying (attempt {tries}/{max_tries})"
        )
        if tries < max_tries:
            return get_valid_ai_note(
                title, timestamp, note, transcript, tries + 1, max_tries
            )
        else:
            print(f"Max retries reached for note ID {note.get('id')}")
            return ai_note
    print(f"Generated valid AI note with length {len(ai_note)}")
    return ai_note


def lambda_handler(event, context):
    """AWS Lambda handler function"""
    print("Lambda function started")
    print(f"Event received: {json.dumps(event)}")
    try:
        # Check authorization
        headers = event.get("headers", {})
        if not check_authorization(headers):
            print("Authorization failed")
            return {"statusCode": 401, "body": json.dumps({"error": "Unauthorized"})}

        # Get note data from the event
        note_data = event.get("body", {})
        if isinstance(note_data, str):
            note_data = json.loads(note_data)
        print(f"Note data: {json.dumps(note_data)}")

        if not note_data:
            print("No data provided in request")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "No data provided"}),
            }

        # Extract required fields
        note_id = note_data.get("id")
        video_id = note_data.get("video_id")
        video_title = note_data.get("video_title")
        note_timestamp = note_data.get("note_timestamp")
        print(
            f"Extracted fields - Note ID: {note_id}, Video ID: {video_id}, Timestamp: {note_timestamp}"
        )

        if not all([note_id, video_id, video_title, note_timestamp]):
            print("Missing required fields")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing required fields"}),
            }

        # Get transcript
        transcript = get_transcript(video_id)
        if not transcript:
            print("Transcript not found")
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Transcript not found"}),
            }

        # Get relevant transcript portion
        relevant_transcript = get_relevant_transcript(transcript, note_timestamp)
        if not relevant_transcript:
            print("No relevant transcript found")
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "No relevant transcript found"}),
            }

        # Generate AI note
        ai_note = get_valid_ai_note(
            video_title, note_timestamp, note_data, relevant_transcript
        )
        if not ai_note:
            print("Failed to generate AI note")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Failed to generate AI note"}),
            }

        # Update note with AI note using PATCH request
        update_url = f"{BASE_URL}/notes/{note_id}"
        print(f"Updating note at URL: {update_url}")
        try:
            response = requests.patch(
                update_url, json={"ai_note": ai_note}, timeout=120
            )
            response.raise_for_status()
            update_response = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Failed to update note: {e}")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": f"Failed to update note: {str(e)}"}),
            }

        print("Successfully completed note generation and update")
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
        print(f"Unexpected error in lambda handler: {str(e)}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
