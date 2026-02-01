from typing import Any, Dict, List, Optional
import json
import os
import boto3
import requests
from aws_lambda_powertools import Logger

# Configuration
VIDWIZ_HOST = os.getenv("VIDWIZ_HOST", "vidwiz.online/api")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")
ADMIN_AUTH_TOKEN = os.getenv("ADMIN_AUTH_TOKEN")


assert SQS_QUEUE_URL, "SQS_QUEUE_URL is not set"
assert ADMIN_AUTH_TOKEN, "ADMIN_AUTH_TOKEN is not set"


logger = Logger()


def extract_valid_video_id(key: str) -> Optional[str]:
    try:
        video_id = key.split("/")[-1].replace(".json", "")
        return video_id
    except Exception as e:
        logger.error(f"Error extracting video_id: {e}")
        return None


def fetch_all_notes(video_id: str) -> Optional[List[Dict[str, Any]]]:
    url = f"https://{VIDWIZ_HOST}/videos/{video_id}/notes/ai-note-task"
    headers = {"Authorization": f"Bearer {ADMIN_AUTH_TOKEN}"}
    try:
        resp = requests.get(url, headers=headers)
        logger.info(f"Status code from vidwiz: {resp.status_code}")
        logger.info(f"Response from vidwiz: {resp.text}")
        if resp.status_code == 200:
            return resp.json().get("notes", [])
        logger.error(f"Error while getting notes for video {video_id}")
        return None
    except Exception as e:
        logger.error(f"Exception while fetching notes: {e}")
        return None


def chunk_list(items: List[Dict[str, Any]], size: int) -> List[List[Dict[str, Any]]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def push_notes_to_sqs_batch(notes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Send notes to SQS in batches of 10 (SQS limit)."""
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


@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: Dict[str, Any], context: Any):
    try:
        records = event.get("Records", [])
        if not records:
            logger.error("No S3 event records found")
            return

        key = records[0]["s3"]["object"]["key"]
        video_id = extract_valid_video_id(key)
        if not video_id:
            logger.error(f"Error getting video_id from key {key}")
            return

        notes_data = fetch_all_notes(video_id)
        if not notes_data:
            logger.info(
                "No notes to enqueue for this video", extra={"video_id": video_id}
            )
            return

        result = push_notes_to_sqs_batch(notes_data)
        logger.info("Enqueue to SQS completed", extra={"video_id": video_id, **result})
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
