from typing import Any

from vidwiz_worker.clients import InternalApiClient, OpenRouterClient
from vidwiz_worker.config import WorkerSettings
from vidwiz_worker.models import Note, SummaryRequest
from vidwiz_worker.transcript import (
    S3TranscriptRepository,
    build_transcript_text,
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

SUMMARY_PROMPT_TEMPLATE = """Generate a clear and concise summary of the following video transcript.

The summary should be between {min_length} and {max_length} characters.
Capture the key ideas, explanations, and conclusions.
Do not include timestamps, formatting, bullet points, or extra commentary.

{title_block}Transcript:
{transcript}

Even if the transcript is in any language, generate the summary in English.
Return only the summary text, without any additional text or formatting.
"""


class AiNoteService:
    def __init__(
        self,
        settings: WorkerSettings,
        logger: Any,
        *,
        transcripts: S3TranscriptRepository | None = None,
        api: InternalApiClient | None = None,
        llm: OpenRouterClient | None = None,
    ):
        self._settings = settings
        self._logger = logger
        self._transcripts = transcripts or S3TranscriptRepository(settings, logger)
        self._api = api or InternalApiClient(settings, logger)
        self._llm = llm or OpenRouterClient(settings, logger)

    def process_batch(self, notes: list[Note]) -> None:
        self._logger.info("Starting note processing", extra={"note_count": len(notes)})
        for index, note in enumerate(notes, start=1):
            self._logger.info(
                "Processing note batch item",
                extra={
                    "item_index": index,
                    "total_items": len(notes),
                    "note_id": note.id,
                },
            )
            try:
                self.process(note)
            except Exception as error:
                self._logger.error(
                    "Failed to process note",
                    extra={"note_id": note.id, "error": str(error)},
                )
        self._logger.info(
            "Completed note processing batch", extra={"processed_count": len(notes)}
        )

    def process(self, note: Note) -> None:
        transcript = self._transcripts.get(note.video_id)
        if not transcript:
            self._logger.error(
                "Cannot process note - transcript not available",
                extra={"video_id": note.video_id, "note_id": note.id},
            )
            return
        context = relevant_context(transcript, note.timestamp, self._settings)
        if context is None:
            self._logger.error(
                "Cannot process note - relevant transcript not found",
                extra={
                    "video_id": note.video_id,
                    "note_id": note.id,
                    "timestamp": note.timestamp,
                },
            )
            return
        title = note.video.title if note.video and note.video.title else None
        if title is None:
            metadata = self._api.get_video(note.video_id)
            title = metadata.get("title") if metadata else None
        note_text = self._valid_note(title, note.timestamp, format_context(context))
        if note_text:
            self._api.update_note(note.id, note_text)
        else:
            self._logger.error("Failed to generate AI note", extra={"note_id": note.id})

    def _valid_note(
        self, title: str | None, timestamp: str, transcript: str
    ) -> str | None:
        for attempt in range(1, self._settings.max_retries + 1):
            prompt = NOTE_PROMPT_TEMPLATE.format(
                max_length=self._settings.max_note_length,
                title_block=f"Title: {title}\n" if title else "",
                timestamp=timestamp,
                timestamp_seconds=parse_timestamp_seconds(timestamp),
                transcript=transcript.replace("{", "{{").replace("}", "}}"),
            )
            generated = self._llm.complete(prompt)
            if generated is None:
                return None
            generated = generated.strip().replace("\n", " ")
            if (
                self._settings.min_note_length
                <= len(generated)
                <= self._settings.max_note_length
            ):
                return generated
            if attempt == self._settings.max_retries:
                return generated
        return None


class AiSummaryService:
    def __init__(
        self,
        settings: WorkerSettings,
        logger: Any,
        *,
        transcripts: S3TranscriptRepository | None = None,
        api: InternalApiClient | None = None,
        llm: OpenRouterClient | None = None,
    ):
        self._settings = settings
        self._logger = logger
        self._transcripts = transcripts or S3TranscriptRepository(settings, logger)
        self._api = api or InternalApiClient(settings, logger)
        self._llm = llm or OpenRouterClient(settings, logger)

    def process_batch(self, requests: list[SummaryRequest]) -> None:
        self._logger.info(
            "Starting summary processing", extra={"request_count": len(requests)}
        )
        for index, request in enumerate(requests, start=1):
            self._logger.info(
                "Processing summary batch item",
                extra={
                    "item_index": index,
                    "total_items": len(requests),
                    "video_id": request.video_id,
                },
            )
            try:
                self.process(request.video_id)
            except Exception as error:
                self._logger.error(
                    "Failed to process summary",
                    extra={"video_id": request.video_id, "error": str(error)},
                )
        self._logger.info(
            "Completed summary processing batch",
            extra={"processed_count": len(requests)},
        )

    def process(self, video_id: str) -> None:
        video = self._api.get_video(video_id)
        if not video:
            self._logger.error(
                "Failed to fetch video details, cannot proceed",
                extra={"video_id": video_id},
            )
            return
        if video.get("summary"):
            self._logger.info(
                "Summary already exists for video, skipping generation",
                extra={"video_id": video_id},
            )
            return
        transcript = self._transcripts.get(video_id)
        if not transcript:
            self._logger.error(
                "Cannot process summary - transcript not available",
                extra={"video_id": video_id},
            )
            return
        summary = self._valid_summary(
            video.get("title"),
            build_transcript_text(transcript, include_timestamps=False),
        )
        if summary:
            self._api.update_summary(video_id, summary)
        else:
            self._logger.error(
                "Failed to generate AI summary", extra={"video_id": video_id}
            )

    def _valid_summary(self, title: str | None, transcript: str) -> str | None:
        for attempt in range(1, self._settings.max_retries + 1):
            prompt = SUMMARY_PROMPT_TEMPLATE.format(
                min_length=self._settings.min_summary_length,
                max_length=self._settings.max_summary_length,
                title_block=f"Title: {title}\n\n" if title else "",
                transcript=transcript.replace("{", "{{").replace("}", "}}"),
            )
            generated = self._llm.complete(prompt)
            if generated is None:
                return None
            generated = generated.strip().replace("\n", " ")
            if (
                self._settings.min_summary_length
                <= len(generated)
                <= self._settings.max_summary_length
            ):
                return generated
            if attempt == self._settings.max_retries:
                return generated
        return None
