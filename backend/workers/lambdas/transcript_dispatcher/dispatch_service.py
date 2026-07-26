import json
import os
from typing import Any, Dict, List, Optional

import boto3
import requests
from aws_lambda_powertools import Logger

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
        if response.status_code == 200:
            notes = response.json().get("notes", [])
            logger.info(
                "Fetched AI note tasks",
                extra={
                    "video_id": video_id,
                    "status_code": response.status_code,
                    "note_count": len(notes),
                },
            )
            return notes
        if response.status_code == 404:
            logger.info(
                "No eligible AI notes found",
                extra={"video_id": video_id},
            )
            return []
        logger.error(
            "Failed to fetch AI note tasks",
            extra={
                "video_id": video_id,
                "status_code": response.status_code,
            },
        )
    except Exception as error:
        logger.error(
            "Error fetching AI note tasks",
            extra={
                "video_id": video_id,
                "error_type": type(error).__name__,
            },
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
                "Sent AI note batch to SQS",
                extra={
                    "batch_index": batch_index,
                    "sent": len(successful),
                    "failed": len(failed),
                },
            )
            if failed:
                logger.error(
                    "Some AI note messages failed to send",
                    extra={
                        "batch_index": batch_index,
                        "failed": len(failed),
                    },
                )
            results.append(response)
        except Exception as error:
            total_failed += len(entries)
            logger.error(
                "Failed to send AI note batch to SQS",
                extra={
                    "batch_index": batch_index,
                    "failed": len(entries),
                    "error_type": type(error).__name__,
                },
            )

    return {"sent": total_sent, "failed": total_failed, "batches": len(results)}


def push_summary_to_sqs(video_id: str) -> bool:
    if not SQS_AI_SUMMARY_QUEUE_URL:
        logger.error(
            "Summary queue is not configured",
            extra={"video_id": video_id},
        )
        return False

    sqs = boto3.client("sqs")
    try:
        sqs.send_message(
            QueueUrl=SQS_AI_SUMMARY_QUEUE_URL,
            MessageBody=json.dumps({"video_id": video_id}),
        )
        logger.info(
            "Sent AI summary request to SQS",
            extra={"video_id": video_id},
        )
        return True
    except Exception as error:
        logger.error(
            "Failed to send AI summary request to SQS",
            extra={
                "video_id": video_id,
                "error_type": type(error).__name__,
            },
        )
        return False


def dispatch_videos(video_ids: List[str], dispatch_summary: bool) -> None:
    for video_id in video_ids:
        logger.info(
            "Processing video dispatch",
            extra={"video_id": video_id},
        )

        if dispatch_summary:
            push_summary_to_sqs(video_id)

        notes = fetch_all_notes(video_id)
        if notes is None:
            continue
        if not notes:
            logger.info(
                "No AI notes to dispatch",
                extra={"video_id": video_id},
            )
            continue

        result = push_notes_to_sqs_batch(notes)
        logger.info(
            "Completed AI note dispatch",
            extra={
                "video_id": video_id,
                "sent": result["sent"],
                "failed": result["failed"],
            },
        )
