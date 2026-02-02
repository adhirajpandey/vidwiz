from aws_lambda_powertools import Logger
from typing import Any, Dict, List, Optional
import json
import os
import boto3
import requests

# Configuration constants
VIDWIZ_ENDPOINT = os.getenv("VIDWIZ_ENDPOINT")
VIDWIZ_TOKEN = os.getenv("VIDWIZ_TOKEN")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")

assert VIDWIZ_ENDPOINT, "VIDWIZ_ENDPOINT is not set"
assert VIDWIZ_TOKEN, "VIDWIZ_TOKEN is not set"
assert SQS_QUEUE_URL, "SQS_QUEUE_URL is not set"

logger = Logger()


# Utility Functions
def extract_valid_video_id(key: str) -> Optional[str]:
    """
    Extract a valid video ID from an S3 object key.

    Args:
        key: S3 object key (e.g. "transcripts/abc123.json" or "path/to/abc123.json").

    Returns:
        The video ID (filename without .json), or None if extraction fails.
    """
    try:
        video_id = key.split("/")[-1].replace(".json", "")
        return video_id
    except Exception as e:
        logger.error("Error extracting video_id", extra={"error": str(e)})
        return None


def fetch_all_notes(video_id: str) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch all AI-note tasks for a video from the VidWiz API.

    Args:
        video_id: Unique identifier for the video.

    Returns:
        List of note task dicts, or None if the request fails or returns non-200.
    """
    # Use api/v2/internal
    url = f"{VIDWIZ_ENDPOINT}/v2/internal/videos/{video_id}/ai-notes"
    headers = {"Authorization": f"Bearer {VIDWIZ_TOKEN}"}
    try:
        resp = requests.get(url, headers=headers)
        logger.info("VidWiz response received", extra={"video_id": video_id, "status_code": resp.status_code, "response_preview": resp.text[:200] if resp.text else ""})
        if resp.status_code == 200:
            return resp.json().get("notes", [])
        logger.error("Error while getting notes for video", extra={"video_id": video_id, "status_code": resp.status_code})
        return None
    except Exception as e:
        logger.error("Exception while fetching notes", extra={"video_id": video_id, "error": str(e)})
        return None


def chunk_list(items: List[Dict[str, Any]], size: int) -> List[List[Dict[str, Any]]]:
    """
    Split a list into sublists of at most the given size.

    Args:
        items: List of items to chunk.
        size: Maximum number of items per chunk.

    Returns:
        List of chunks; each chunk is a list of at most `size` items.
    """
    return [items[i : i + size] for i in range(0, len(items), size)]


def push_notes_to_sqs_batch(notes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Send note tasks to SQS in batches of 10 (SQS send_message_batch limit).

    Args:
        notes: List of note task dicts to enqueue.

    Returns:
        Dict with keys: "sent" (count of successful messages), "failed" (count of failed),
        "batches" (number of batch requests made). Does not raise; failures are logged.
    """
    sqs = boto3.client("sqs")
    total_sent = 0
    total_failed = 0
    results: List[Dict[str, Any]] = []

    for batch_index, batch in enumerate(chunk_list(notes, 10)):
        entries: List[Dict[str, Any]] = []
        for i, note in enumerate(batch):
            entry: Dict[str, Any] = {
                "Id": str(i),
                "MessageBody": json.dumps(note),
            }
            entries.append(entry)
        try:
            resp = sqs.send_message_batch(QueueUrl=SQS_QUEUE_URL, Entries=entries)
            failed = resp.get("Failed", [])
            successful = resp.get("Successful", [])
            total_sent += len(successful)
            total_failed += len(failed)
            logger.info(
                "SQS batch send result",
                extra={
                    "batch_index": batch_index,
                    "sent": len(successful),
                    "failed": len(failed),
                },
            )
            if failed:
                logger.error("SQS batch failed entries", extra={"failed": failed})
            results.append(resp)
        except Exception as e:
            total_failed += len(entries)
            logger.error(
                "Exception while sending SQS batch",
                extra={"batch_index": batch_index, "error": str(e)},
            )

    return {"sent": total_sent, "failed": total_failed, "batches": len(results)}


def push_summary_to_sqs(video_id: str) -> bool:
    """
    Send a summary generation request to the AI Summary SQS queue.
    """
    if not SQS_SUMMARY_QUEUE_URL:
        logger.warning("SQS_SUMMARY_QUEUE_URL is not set, skipping summary dispatch")
        return False

    sqs = boto3.client("sqs")
    message_body = json.dumps({"video_id": video_id})
    
    try:
        sqs.send_message(QueueUrl=SQS_SUMMARY_QUEUE_URL, MessageBody=message_body)
        logger.info("Dispatched summary request", extra={"video_id": video_id})
        return True
    except Exception as e:
        logger.error("Failed to dispatch summary request", extra={"video_id": video_id, "error": str(e)})
        return False


# Lambda Entry Point
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: Dict[str, Any], context: Any):
    """
    Task Dispatcher Lambda Handler.

    Triggered by:
    - **S3 Event**: When a transcript JSON is saved to `transcripts/`.
      - Actions:
        1. Dispatches a `SummaryRequest` to the AI Summary SQS Queue.
        2. Fetches pending AI Note tasks from VidWiz API and pushes them to the AI Note SQS Queue.
    - **Manual**: Via `event["video_ids"]` (list of strings).
      - Actions: Runs the dispatch logic for the specified videos.

    Args:
        event: S3 event dict (Records) or manual invocation dict (video_ids).
        context: Lambda context (unused).

    Returns:
        None. Failures are logged; no exception is raised.
    """
        context: Lambda context (unused).

    Returns:
        None. Failures are logged; no exception is raised.
    """
    try:
        # Collect video IDs from either S3 event or manual input
        video_ids: List[str] = []
        is_s3_event = False

        # 1️⃣ S3 Event Mode
        records = event.get("Records", [])
        if records and isinstance(records, list):
            first = records[0]
            if "s3" in first and "object" in first["s3"]:
                is_s3_event = True
                key = first["s3"]["object"]["key"]
                video_id = extract_valid_video_id(key)
                if video_id:
                    video_ids.append(video_id)
                else:
                    logger.error(f"Could not extract video_id from key: {key}")

        # 2️⃣ Manual Mode (via event["video_ids"])
        incoming_ids = event.get("video_ids")
        if incoming_ids:
            if isinstance(incoming_ids, list):
                video_ids.extend(incoming_ids)
            else:
                logger.error("`video_ids` field must be a list of strings")

        # If no video IDs found, exit
        if not video_ids:
            logger.error("No video IDs found in the event")
            return

        # Process all video IDs
        for vid in video_ids:
            logger.info(f"Processing video_id: {vid}")

            # Dispatch Summary Task (Only for S3 events usually, but safe to force for manual too if desired)
            # We treat S3 event as "Transcript Available" signal -> TRIGGER ALL DOWNSTREAM
            if is_s3_event:
                push_summary_to_sqs(vid)

            # Dispatch Note Tasks
            notes_data = fetch_all_notes(vid)
            if notes_data is None:
                logger.error(f"Failed to fetch notes for video {vid}")
                continue

            if not notes_data:
                logger.info("No notes to enqueue", extra={"video_id": vid})
                continue

            result = push_notes_to_sqs_batch(notes_data)
            logger.info(
                "Enqueue to SQS completed",
                extra={"video_id": vid, **result},
            )
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
