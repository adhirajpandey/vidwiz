import math

from aws_lambda_powertools import Logger

from vidwiz_worker.clients import InternalApiClient, OpenRouterClient
from vidwiz_worker.config import WorkerSettings
from vidwiz_worker.jobs import (
    InvalidOutputError,
    PermanentError,
    ProviderError,
    run_job,
)
from vidwiz_worker.models import Moment
from vidwiz_worker.transcript import (
    S3TranscriptRepository,
    format_context,
    format_mm_ss,
    relevant_context,
)

NOTE_PROMPT_TEMPLATE = """Generate a concise one-line note based on the provided title, timestamp, and transcript.
The note should be less than {max_length} characters and capture the essence of the content at the specified timestamp.
The viewer captured this moment just after hearing it, so weigh what was said shortly before the timestamp.
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
llm = OpenRouterClient(settings, logger, model=settings.ai_note_model)


def process_job(moment: Moment, attempt: int) -> None:
    run_job(
        lambda: process_moment(moment),
        lambda: (
            api.save_moment_ai(moment.id, None, correlation_id=moment.correlation_id)
            if moment.correlation_id
            else api.save_moment_ai(moment.id, None)
        ),
        attempt=attempt,
        max_attempts=settings.max_attempts,
        logger=logger,
        extra={
            "moment_id": moment.id,
            "video_id": moment.video_id,
            "correlation_id": moment.correlation_id,
        },
        report=lambda reason, attempt, final: api.report_attempt_failure(
            "ai_moment", reason, attempt, final, moment.correlation_id
        ),
    )


def process_moment(moment: Moment) -> None:
    """Generate and store one AI line.

    A missing transcript, empty context, or output that stays invalid is
    permanent. Model and network errors raise, so SQS retries the record.
    """
    extra = {
        "moment_id": moment.id,
        "video_id": moment.video_id,
        "correlation_id": moment.correlation_id,
    }
    logger.info("Processing AI moment", extra=extra)
    transcript = transcripts.get(moment.video_id)
    context = (
        relevant_context(transcript, moment.at_seconds, settings)
        if transcript
        else None
    )
    if context is None:
        raise PermanentError("No transcript context for the moment")

    metadata = (
        api.get_video(moment.video_id, moment.correlation_id)
        if moment.correlation_id
        else api.get_video(moment.video_id)
    )
    raw_duration = ((metadata or {}).get("video_metadata") or {}).get("duration")
    try:
        duration = float(raw_duration) if not isinstance(raw_duration, bool) else 0
    except (ValueError, TypeError, OverflowError):
        duration = 0
    if math.isfinite(duration) and duration > 0 and moment.at_seconds > duration:
        saved = api.save_moment_ai(
            moment.id, None, correlation_id=moment.correlation_id
        )
        if not saved:
            raise RuntimeError("Could not flag invalid capture timestamp")
        logger.info("Skipped capture past video end", extra=extra)
        return
    title = metadata.get("title") if metadata else None
    ai_text = _valid_note(title, moment.at_seconds, format_context(context))
    saved = (
        api.save_moment_ai(
            moment.id, ai_text, settings.ai_note_model, moment.correlation_id
        )
        if moment.correlation_id
        else api.save_moment_ai(moment.id, ai_text, settings.ai_note_model)
    )
    if not saved:
        raise RuntimeError(f"Failed to save AI moment {moment.id}")
    logger.info("AI moment saved", extra=extra)


def _valid_note(title: str | None, at_seconds: int, transcript: str) -> str:
    for attempt in range(1, settings.max_retries + 1):
        prompt = NOTE_PROMPT_TEMPLATE.format(
            max_length=settings.max_note_length,
            title_block=f"Title: {title}\n" if title else "",
            timestamp=format_mm_ss(at_seconds),
            timestamp_seconds=at_seconds,
            transcript=transcript.replace("{", "{{").replace("}", "}}"),
        )
        generated = llm.complete(prompt)
        if generated is None:
            # The request failed, not the output; SQS retries the job later.
            raise ProviderError(
                getattr(llm, "last_failure_kind", None) or "provider_error"
            )
        generated = generated.strip().replace("\n", " ")
        if settings.min_note_length <= len(generated) <= settings.max_note_length:
            return generated
        logger.warning(
            "Generated AI note has invalid length",
            extra={
                "attempt": attempt,
                "max_retries": settings.max_retries,
                "generated_length": len(generated),
            },
        )
    raise InvalidOutputError("Generated AI notes kept an invalid length")
