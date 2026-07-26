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
    logger.info("Starting summary processing", extra={"request_count": len(requests)})
    for index, request in enumerate(requests, start=1):
        logger.info(
            "Processing summary batch item",
            extra={
                "item_index": index,
                "total_items": len(requests),
                "video_id": request.video_id,
            },
        )
        try:
            process_summary(request.video_id)
        except Exception as error:
            logger.error(
                "Failed to process summary",
                extra={"video_id": request.video_id, "error": str(error)},
            )
    logger.info(
        "Completed summary processing batch",
        extra={"processed_count": len(requests)},
    )


def process_summary(video_id: str) -> None:
    video = api.get_video(video_id)
    if not video:
        logger.error(
            "Failed to fetch video details, cannot proceed",
            extra={"video_id": video_id},
        )
        return
    if video.get("summary"):
        logger.info(
            "Summary already exists for video, skipping generation",
            extra={"video_id": video_id},
        )
        return
    transcript = transcripts.get(video_id)
    if not transcript:
        logger.error(
            "Cannot process summary - transcript not available",
            extra={"video_id": video_id},
        )
        return
    summary = _valid_summary(
        video.get("title"),
        build_transcript_text(transcript, include_timestamps=False),
    )
    if summary:
        api.update_summary(video_id, summary)
    else:
        logger.error("Failed to generate AI summary", extra={"video_id": video_id})


def _valid_summary(title: str | None, transcript: str) -> str | None:
    for attempt in range(1, settings.max_retries + 1):
        prompt = SUMMARY_PROMPT_TEMPLATE.format(
            min_length=settings.min_summary_length,
            max_length=settings.max_summary_length,
            title_block=f"Title: {title}\n\n" if title else "",
            transcript=transcript.replace("{", "{{").replace("}", "}}"),
        )
        generated = llm.complete(prompt)
        if generated is None:
            return None
        generated = generated.strip().replace("\n", " ")
        if settings.min_summary_length <= len(generated) <= settings.max_summary_length:
            return generated
        if attempt == settings.max_retries:
            return generated
    return None
