"""Transcript storage in S3 and the transcript helpers shared by domains."""

import json
import logging
import math

import boto3


logger = logging.getLogger(__name__)

# A moment's quote covers what was said just before the capture, since people
# capture after hearing something, plus a little after.
QUOTE_SECONDS_BEFORE = 10
QUOTE_SECONDS_AFTER = 5
QUOTE_MAX_CHARS = 350
PASSAGE_MAX_CHARS = 1400

# Searchable passages: long enough to hold an idea, short enough to cite.
CHUNK_TARGET_SECONDS = 45


def _s3_client():
    from src.config import settings

    return boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )


def _key(video_id: str) -> str:
    return f"transcripts/{video_id}.json"


def load_transcript(video_id: str) -> list | None:
    from src.config import settings

    logger.debug("Fetching transcript from S3", extra={"video_id": video_id})
    if not settings.s3_transcript_bucket_name:
        return None
    try:
        response = _s3_client().get_object(
            Bucket=settings.s3_transcript_bucket_name, Key=_key(video_id)
        )
        transcript = json.loads(response["Body"].read().decode("utf-8"))
        logger.debug("Fetched transcript from S3", extra={"video_id": video_id})
        return transcript
    except Exception as exc:
        logger.warning("Transcript fetch failed", extra={"error": str(exc)})
        return None


def store_transcript(video_id: str, transcript: list[dict]) -> None:
    from src.config import settings

    logger.debug("Storing transcript in S3", extra={"video_id": video_id})
    bucket = settings.s3_transcript_bucket_name
    if not bucket:
        logger.debug("S3 bucket not configured", extra={"video_id": video_id})
        return
    _s3_client().put_object(
        Bucket=bucket,
        Key=_key(video_id),
        Body=json.dumps(transcript).encode("utf-8"),
        ContentType="application/json",
    )
    logger.debug("Stored transcript in S3", extra={"video_id": video_id})


def segment_times(item: dict) -> tuple[float, float] | None:
    try:
        start = float(item.get("offset", item.get("start")))
    except (TypeError, ValueError):
        return None
    try:
        duration = float(item.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if not math.isfinite(start) or start < 0:
        return None
    return start, start + max(duration, 0.0)


def quote_for(transcript: list, at_seconds: int) -> tuple[str, int] | None:
    """Return the transcript text around a capture and where it starts."""
    window_start = at_seconds - QUOTE_SECONDS_BEFORE
    window_end = at_seconds + QUOTE_SECONDS_AFTER
    pieces: list[tuple[float, str]] = []
    for item in transcript:
        if not isinstance(item, dict):
            continue
        times = segment_times(item)
        text = " ".join(str(item.get("text") or "").split())
        if times is None or not text:
            continue
        start, end = times
        if end >= window_start and start <= window_end:
            pieces.append((start, text))
    if not pieces:
        return None
    pieces.sort(key=lambda piece: piece[0])
    quote = " ".join(text for _, text in pieces)
    if len(quote) > QUOTE_MAX_CHARS:
        # Keep the end: it is closest to the moment of capture.
        quote = "…" + quote[-(QUOTE_MAX_CHARS - 1) :].split(" ", 1)[-1]
    return quote, int(pieces[0][0])


def chunk_transcript(transcript: list) -> list[tuple[int, int, str]]:
    """Group transcript segments into ~45-second passages.

    Returns (start_seconds, end_seconds, text) tuples in playback order.
    Segments without valid timing or text are skipped.
    """
    segments = []
    for item in transcript:
        if not isinstance(item, dict):
            continue
        times = segment_times(item)
        text = " ".join(str(item.get("text") or "").split())
        if times is not None and text:
            segments.append((times[0], times[1], text))
    segments.sort(key=lambda segment: segment[0])

    chunks: list[tuple[int, int, str]] = []
    current: list[tuple[float, float, str]] = []
    for segment in segments:
        if current and segment[0] - current[0][0] >= CHUNK_TARGET_SECONDS:
            chunks.append(_close_chunk(current))
            current = []
        current.append(segment)
    if current:
        chunks.append(_close_chunk(current))
    return chunks


def _close_chunk(segments: list[tuple[float, float, str]]) -> tuple[int, int, str]:
    start = int(segments[0][0])
    end = max(start, int(math.ceil(max(segment[1] for segment in segments))))
    return start, end, " ".join(segment[2] for segment in segments)


def text_between(
    transcript: list, start_seconds: float, end_seconds: float
) -> str | None:
    """Transcript text overlapping a cited range, for saving a passage."""
    pieces = []
    for item in transcript:
        if not isinstance(item, dict):
            continue
        times = segment_times(item)
        text = " ".join(str(item.get("text") or "").split())
        if times and text and times[1] >= start_seconds and times[0] <= end_seconds:
            pieces.append((times[0], text))
    if not pieces:
        return None
    pieces.sort(key=lambda piece: piece[0])
    return " ".join(text for _, text in pieces)[:PASSAGE_MAX_CHARS]
