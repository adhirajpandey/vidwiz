from typing import Any

import boto3

from vidwiz_worker.config import WorkerSettings
from vidwiz_worker.models import RelevantTranscriptContext, TranscriptSegment


def format_mm_ss(seconds: float) -> str:
    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)
    return f"{minutes}:{remaining_seconds:02d}"


def build_transcript_text(
    transcript: list[dict[str, Any]], *, include_timestamps: bool = True
) -> str:
    lines = []
    for segment in transcript:
        if "text" not in segment:
            continue
        text = segment["text"]
        if include_timestamps and "offset" in segment:
            lines.append(f"{format_mm_ss(float(segment['offset']))} {text}")
        else:
            lines.append(text)
    return "\n".join(lines) if include_timestamps else " ".join(lines)


def parse_timestamp_seconds(timestamp: str) -> int:
    try:
        parts = [int(part) for part in timestamp.split(":")]
        if len(parts) not in (2, 3):
            raise ValueError(timestamp)
        return sum(value * 60**index for index, value in enumerate(reversed(parts)))
    except Exception as error:
        raise ValueError(f"Invalid timestamp format: {timestamp}") from error


def relevant_context(
    transcript: list[dict[str, Any]], timestamp: str, settings: WorkerSettings
) -> RelevantTranscriptContext | None:
    timestamp_seconds = parse_timestamp_seconds(timestamp)
    relevant = [
        segment
        for segment in transcript
        if (timestamp_seconds - settings.transcript_buffer_seconds)
        <= float(segment["offset"])
        <= (timestamp_seconds + settings.transcript_buffer_seconds)
    ]
    if not relevant:
        return None

    closest_index = min(
        range(len(transcript)),
        key=lambda index: abs(float(transcript[index]["offset"]) - timestamp_seconds),
    )
    start_index = max(0, closest_index - settings.context_segments)
    end_index = closest_index + settings.context_segments + 1
    return RelevantTranscriptContext(
        timestamp=float(transcript[closest_index]["offset"]),
        text=transcript[closest_index]["text"],
        before=[
            TranscriptSegment(offset=float(segment["offset"]), text=segment["text"])
            for segment in transcript[start_index:closest_index]
        ],
        after=[
            TranscriptSegment(offset=float(segment["offset"]), text=segment["text"])
            for segment in transcript[closest_index + 1 : end_index]
        ],
    )


def format_context(context: RelevantTranscriptContext) -> str:
    parts = []
    if context.before:
        parts.append(
            build_transcript_text(
                [{"text": segment.text} for segment in context.before],
                include_timestamps=False,
            )
        )
    parts.append(f"[{context.text}]")
    if context.after:
        parts.append(
            build_transcript_text(
                [{"text": segment.text} for segment in context.after],
                include_timestamps=False,
            )
        )
    return " ".join(parts)


class S3TranscriptRepository:
    def __init__(self, settings: WorkerSettings, logger: Any, *, s3_client: Any = None):
        self._settings = settings
        self._logger = logger
        self._s3_client = s3_client or boto3.client("s3")

    def get(self, video_id: str) -> list[dict[str, Any]] | None:
        transcript_key = f"transcripts/{video_id}.json"
        for attempt in range(1, self._settings.transcript_fetch_max_retries + 1):
            try:
                response = self._s3_client.get_object(
                    Bucket=self._settings.transcript_bucket_name, Key=transcript_key
                )
                import json

                transcript = json.loads(response["Body"].read().decode("utf-8"))
                if transcript is None or not isinstance(transcript, list):
                    self._logger.warning(
                        "Transcript payload is invalid",
                        extra={"video_id": video_id, "attempt": attempt},
                    )
                    return None
                self._logger.info(
                    "Successfully loaded transcript from S3",
                    extra={"video_id": video_id, "segment_count": len(transcript)},
                )
                return transcript
            except Exception as error:
                self._logger.warning(
                    "Failed to get transcript from S3",
                    extra={
                        "video_id": video_id,
                        "attempt": attempt,
                        "max_retries": self._settings.transcript_fetch_max_retries,
                        "error": str(error),
                    },
                )
                if attempt < self._settings.transcript_fetch_max_retries:
                    import time

                    time.sleep(self._settings.transcript_fetch_retry_delay)
        self._logger.error(
            "Max retries reached for transcript fetch", extra={"video_id": video_id}
        )
        return None
