from typing import Any, Dict, List, Optional
import json
import os

from aws_lambda_powertools import Logger
import boto3
import requests

VIDWIZ_INTERNAL_API_BASE_URL = os.getenv("VIDWIZ_INTERNAL_API_BASE_URL")
VIDWIZ_INTERNAL_API_ADMIN_TOKEN = os.getenv("VIDWIZ_INTERNAL_API_ADMIN_TOKEN")
SQS_AI_NOTE_QUEUE_URL = os.getenv("SQS_AI_NOTE_QUEUE_URL")
SQS_AI_SUMMARY_QUEUE_URL = os.getenv("SQS_AI_SUMMARY_QUEUE_URL")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

assert VIDWIZ_INTERNAL_API_BASE_URL, "VIDWIZ_INTERNAL_API_BASE_URL is not set"
assert VIDWIZ_INTERNAL_API_ADMIN_TOKEN, "VIDWIZ_INTERNAL_API_ADMIN_TOKEN is not set"
assert SQS_AI_NOTE_QUEUE_URL, "SQS_AI_NOTE_QUEUE_URL is not set"

logger = Logger()


def fetch_all_notes(video_id: str) -> Optional[List[Dict[str, Any]]]:
    url = f"{VIDWIZ_INTERNAL_API_BASE_URL}/v2/internal/videos/{video_id}/ai-notes"
    headers = {"Authorization": f"Bearer {VIDWIZ_INTERNAL_API_ADMIN_TOKEN}"}
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        logger.info(
            "VidWiz response received",
            extra={
                "video_id": video_id,
                "status_code": response.status_code,
                "response_preview": response.text[:200] if response.text else "",
            },
        )
        if response.status_code == 200:
            return response.json().get("notes", [])
        logger.error(
            "Error while getting notes for video",
            extra={"video_id": video_id, "status_code": response.status_code},
        )
    except Exception as error:
        logger.error(
            "Exception while fetching notes",
            extra={"video_id": video_id, "error": str(error)},
        )
    return None


def chunk_list(items: List[Dict[str, Any]], size: int) -> List[List[Dict[str, Any]]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def push_notes_to_sqs_batch(notes: List[Dict[str, Any]]) -> Dict[str, Any]:
    sqs = boto3.client("sqs")
    total_sent = 0
    total_failed = 0
    results: List[Dict[str, Any]] = []

    for batch_index, batch in enumerate(chunk_list(notes, 10)):
        entries = [
            {"Id": str(index), "MessageBody": json.dumps(note)}
            for index, note in enumerate(batch)
        ]
        try:
            response = sqs.send_message_batch(
                QueueUrl=SQS_AI_NOTE_QUEUE_URL,
                Entries=entries,
            )
            failed = response.get("Failed", [])
            successful = response.get("Successful", [])
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
            results.append(response)
        except Exception as error:
            total_failed += len(entries)
            logger.error(
                "Exception while sending SQS batch",
                extra={"batch_index": batch_index, "error": str(error)},
            )

    return {"sent": total_sent, "failed": total_failed, "batches": len(results)}


def push_summary_to_sqs(video_id: str) -> bool:
    if not SQS_AI_SUMMARY_QUEUE_URL:
        logger.warning("SQS_AI_SUMMARY_QUEUE_URL is not set, skipping summary dispatch")
        return False

    sqs = boto3.client("sqs")
    try:
        sqs.send_message(
            QueueUrl=SQS_AI_SUMMARY_QUEUE_URL,
            MessageBody=json.dumps({"video_id": video_id}),
        )
        logger.info("Dispatched summary request", extra={"video_id": video_id})
        return True
    except Exception as error:
        logger.error(
            "Failed to dispatch summary request",
            extra={"video_id": video_id, "error": str(error)},
        )
        return False


def dispatch_videos(video_ids: List[str], dispatch_summary: bool) -> None:
    for video_id in video_ids:
        logger.info(f"Processing video_id: {video_id}")

        if dispatch_summary:
            push_summary_to_sqs(video_id)

        notes = fetch_all_notes(video_id)
        if notes is None:
            logger.error(f"Failed to fetch notes for video {video_id}")
            continue
        if not notes:
            logger.info("No notes to enqueue", extra={"video_id": video_id})
            continue

        result = push_notes_to_sqs_batch(notes)
        logger.info(
            "Enqueue to SQS completed",
            extra={"video_id": video_id, **result},
        )
