from aws_lambda_powertools import Logger

from vidwiz_worker.clients import InternalApiClient, OpenRouterClient
from vidwiz_worker.config import WorkerSettings
from vidwiz_worker.models import Note
from vidwiz_worker.transcript import (
    S3TranscriptRepository,
    format_context,
    parse_timestamp_seconds,
    relevant_context,
)

NOTE_PROMPT_TEMPLATE = """Generate a concise one-line note based on the provided title, timestamp, and transcript.
The note should be less than {max_length} characters and capture the essence of the content at the specified timestamp.
Focus more on the transcript context than the title. Do not include any additional text or formatting.

Here are the details:
{title_block}Timestamp: {timestamp} - {timestamp_seconds} seconds
Transcript: {transcript}

Even if the transcript is in any language, generate a note in English.
Return only the note, without any additional text or formatting.
Do not add '\",\",-,: any special character anywhere in the note.
"""

logger = Logger()
settings = WorkerSettings.from_env()
transcripts = S3TranscriptRepository(settings, logger)
api = InternalApiClient(settings, logger)
llm = OpenRouterClient(settings, logger)


def process_batch(notes: list[Note]) -> None:
    logger.info("Starting note processing", extra={"note_count": len(notes)})
    for index, note in enumerate(notes, start=1):
        logger.info(
            "Processing note batch item",
            extra={
                "item_index": index,
                "total_items": len(notes),
                "note_id": note.id,
            },
        )
        process_note(note)
    logger.info(
        "Completed note processing batch", extra={"processed_count": len(notes)}
    )


def process_note(note: Note) -> None:
    transcript = transcripts.get(note.video_id)
    if not transcript:
        logger.error(
            "Cannot process note - transcript not available",
            extra={"video_id": note.video_id, "note_id": note.id},
        )
        raise RuntimeError(f"Transcript not available for note {note.id}")
    context = relevant_context(transcript, note.timestamp, settings)
    if context is None:
        logger.error(
            "Cannot process note - relevant transcript not found",
            extra={
                "video_id": note.video_id,
                "note_id": note.id,
                "timestamp": note.timestamp,
            },
        )
        raise RuntimeError(f"Relevant transcript not found for note {note.id}")
    title = note.video.title if note.video and note.video.title else None
    if title is None:
        metadata = api.get_video(note.video_id)
        title = metadata.get("title") if metadata else None
    note_text = _valid_note(title, note.timestamp, format_context(context))
    if not note_text:
        logger.error("Failed to generate AI note", extra={"note_id": note.id})
        raise RuntimeError(f"Failed to generate AI note {note.id}")
    if not api.update_note(note.id, note_text):
        raise RuntimeError(f"Failed to update AI note {note.id}")


def _valid_note(title: str | None, timestamp: str, transcript: str) -> str | None:
    for attempt in range(1, settings.max_retries + 1):
        prompt = NOTE_PROMPT_TEMPLATE.format(
            max_length=settings.max_note_length,
            title_block=f"Title: {title}\n" if title else "",
            timestamp=timestamp,
            timestamp_seconds=parse_timestamp_seconds(timestamp),
            transcript=transcript.replace("{", "{{").replace("}", "}}"),
        )
        generated = llm.complete(prompt)
        if generated is None:
            return None
        generated = generated.strip().replace("\n", " ")
        if settings.min_note_length <= len(generated) <= settings.max_note_length:
            return generated
    return None
