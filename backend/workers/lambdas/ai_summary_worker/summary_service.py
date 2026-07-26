from aws_lambda_powertools import Logger

from vidwiz_worker.clients import InternalApiClient, OpenRouterClient
from vidwiz_worker.config import WorkerSettings
from vidwiz_worker.models import SummaryRequest
from vidwiz_worker.transcript import S3TranscriptRepository, build_transcript_text

SUMMARY_PROMPT_TEMPLATE = """Generate a clear and concise summary of the following video transcript.

The summary should be between {min_length} and {max_length} characters.
Capture the key ideas, explanations, and conclusions.
Do not include timestamps, formatting, bullet points, or extra commentary.

{title_block}Transcript:
{transcript}

Even if the transcript is in any language, generate the summary in English.
Return only the summary text, without any additional text or formatting.
"""

logger = Logger()
settings = WorkerSettings.from_env()
transcripts = S3TranscriptRepository(settings, logger)
api = InternalApiClient(settings, logger)
llm = OpenRouterClient(settings, logger)


def process_batch(requests: list[SummaryRequest]) -> None:
    for request in requests:
        process_summary(request.video_id)


def process_summary(video_id: str) -> None:
    logger.info(
        "Processing AI summary",
        extra={"video_id": video_id},
    )
    video = api.get_video(video_id)
    if not video:
        logger.error("Failed to fetch video details", extra={"video_id": video_id})
        return
    if video.get("summary"):
        logger.info(
            "AI summary already exists; skipping",
            extra={"video_id": video_id},
        )
        return
    transcript = transcripts.get(video_id)
    if not transcript:
        logger.error(
            "Transcript not available for AI summary",
            extra={"video_id": video_id},
        )
        return
    summary = _valid_summary(
        video.get("title"),
        build_transcript_text(transcript, include_timestamps=False),
    )
    if not summary:
        logger.error("Failed to generate AI summary", extra={"video_id": video_id})
        return
    if not api.update_summary(video_id, summary):
        logger.error("Failed to save AI summary", extra={"video_id": video_id})
        return
    logger.info(
        "AI summary saved",
        extra={"video_id": video_id},
    )


def _valid_summary(title: str | None, transcript: str) -> str | None:
    for attempt in range(1, settings.max_retries + 1):
        prompt = SUMMARY_PROMPT_TEMPLATE.format(
            min_length=settings.min_summary_length,
            max_length=settings.max_summary_length,
            title_block=f"Title: {title}\n\n" if title else "",
            transcript=transcript,
        )
        generated = llm.complete(prompt)
        if generated is None:
            return None
        generated = generated.strip().replace("\n", " ")
        if settings.min_summary_length <= len(generated) <= settings.max_summary_length:
            return generated
        logger.warning(
            "Generated AI summary has invalid length",
            extra={
                "attempt": attempt,
                "max_retries": settings.max_retries,
                "generated_length": len(generated),
            },
        )
    return None
