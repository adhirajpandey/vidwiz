import json
import logging
from collections import Counter
from datetime import datetime, timedelta

import boto3
from openai import OpenAI
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.auth.schemas import ViewerContext
from src.config import settings
from src.conversations.models import Conversation, Message
from src.conversations.parts import (
    BlockPart,
    ChunkReference,
    DoneEvent,
    DropReason,
    ErrorEvent,
    ModelResponse,
    ModelResponseV2,
    ModelBlock,
    PartsDecoder,
    stored_parts,
    text_projection,
    transcript_context,
    resolve_block,
    split_block,
    history_parts,
)
from src.conversations.prompts import build_v2_prompt
from src.exceptions import InternalServerError, RateLimitError, NotFoundError
from src.videos.models import Video
from src.videos import service as videos_service

DB_ROLE_USER = "user"
DB_ROLE_ASSISTANT = "assistant"

logger = logging.getLogger(__name__)


def create_conversation(
    db: Session, video_id: str, user_id: int | None, guest_session_id: str | None
) -> Conversation:
    logger.debug(
        "Creating conversation",
        extra={
            "video_id": video_id,
            "user_id": user_id,
            "guest_session": bool(guest_session_id),
        },
    )
    conversation = Conversation(
        video_id=video_id,
        user_id=user_id,
        guest_session_id=guest_session_id,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    logger.debug("Created conversation", extra={"conversation_id": conversation.id})
    return conversation


def get_conversation_for_viewer(
    db: Session, conversation_id: int, viewer: ViewerContext
) -> Conversation | None:
    logger.debug(
        "Fetching conversation for viewer",
        extra={"conversation_id": conversation_id, "user_id": viewer.user_id},
    )
    if viewer.user_id:
        query = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == viewer.user_id,
        )
    else:
        query = select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.guest_session_id == viewer.guest_session_id,
        )
    return db.execute(query).scalar_one_or_none()


def list_messages(db: Session, conversation_id: int) -> list[Message]:
    logger.debug("Listing messages", extra={"conversation_id": conversation_id})
    query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
    )
    return db.execute(query).scalars().all()


def save_chat_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str,
    metadata: dict | None = None,
) -> Message:
    logger.debug(
        "Saving chat message",
        extra={
            "conversation_id": conversation_id,
            "role": role,
            "has_metadata": metadata is not None,
        },
    )
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        metadata_=metadata,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    logger.debug("Saved chat message", extra={"message_id": message.id})
    return message


def fetch_recent_history(
    db: Session, conversation_id: int, limit: int = 10
) -> list[Message]:
    logger.debug(
        "Fetching recent history",
        extra={"conversation_id": conversation_id, "limit": limit},
    )
    query = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    )
    history_msgs = db.execute(query).scalars().all()
    history_msgs.reverse()
    return history_msgs


def check_daily_quota(
    db: Session, user_id: int | None, guest_session_id: str | None
) -> None:
    logger.debug(
        "Checking daily quota",
        extra={"user_id": user_id, "guest_session": bool(guest_session_id)},
    )
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    query = (
        select(func.count())
        .select_from(Message)
        .join(Conversation)
        .where(Message.role == DB_ROLE_USER, Message.created_at >= today)
    )

    if user_id:
        query = query.where(Conversation.user_id == user_id)
        limit = settings.wiz_user_daily_quota
        limit_msg_suffix = "messages/day"
    elif guest_session_id:
        query = query.where(Conversation.guest_session_id == guest_session_id)
        limit = settings.wiz_guest_daily_quota
        limit_msg_suffix = "guest messages/day"
    else:
        return

    msg_count = db.execute(query).scalar_one()
    logger.debug("Quota message count", extra={"count": msg_count, "limit": limit})
    if msg_count >= limit:
        tomorrow_midnight = today + timedelta(days=1)
        now = datetime.utcnow()
        seconds_until_reset = int((tomorrow_midnight - now).total_seconds())
        raise RateLimitError(
            f"Daily limit reached ({limit} {limit_msg_suffix})",
            details={"reset_in_seconds": seconds_until_reset},
        )


def get_transcript_from_s3(video_id: str) -> list | None:
    logger.debug("Fetching transcript from S3", extra={"video_id": video_id})
    if not settings.s3_transcript_bucket_name:
        return None

    transcript_key = f"transcripts/{video_id}.json"
    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )
        response = s3_client.get_object(
            Bucket=settings.s3_transcript_bucket_name,
            Key=transcript_key,
        )
        transcript_data = json.loads(response["Body"].read().decode("utf-8"))
        logger.debug("Fetched transcript from S3", extra={"video_id": video_id})
        return transcript_data
    except Exception as exc:
        logger.warning("Transcript fetch failed", extra={"error": str(exc)})
        return None


def get_valid_transcript_or_raise(
    db: Session, video_id: str
) -> tuple[Video, list] | None:
    logger.debug("Validating transcript availability", extra={"video_id": video_id})
    video = videos_service.get_video_by_id(db, video_id)
    if not video:
        raise NotFoundError("Video not found")

    if not video.transcript_available:
        logger.debug("Transcript not available", extra={"video_id": video_id})
        return None

    transcript = get_transcript_from_s3(video_id)
    if not transcript:
        raise NotFoundError("Transcript data missing")

    return video, transcript


def build_system_instruction(
    video_title: str | None, transcript: list, parts_version: int = 1
) -> str:
    context, _ = transcript_context(transcript)
    template = settings.wiz_system_prompt_template
    if parts_version == 2:
        template = build_v2_prompt(template)
    return template.format(
        title=video_title or "this video",
        transcript=json.dumps(context, ensure_ascii=False),
    )


def log_wiz_structure(
    *,
    blocks_in: int,
    blocks_split: int,
    referenced: set[str],
    resolved: list,
    dropped: Counter,
) -> None:
    """Log how well the model followed the one-element-per-block rule.

    Values go in the message because the production log format omits `extra`.
    """
    blocks = [part for part in resolved if isinstance(part, BlockPart)]
    kept = {
        key
        for block in blocks
        for citation in block.citations
        for passage in citation.passages
        for key in passage.chunk_ids
    }
    drops = " ".join(
        f"dropped_{reason.value}={dropped[reason]}" for reason in DropReason
    )
    logger.info(
        "Wiz structure: model=%s blocks_in=%d blocks_out=%d blocks_split=%d "
        "referenced=%d kept=%d %s",
        settings.wiz_model,
        blocks_in,
        len(blocks),
        blocks_split,
        len(referenced),
        len(kept),
        drops,
    )


def stream_wiz_response(
    *,
    video_title: str | None,
    transcript: list,
    history: list[dict],
    conversation_id: int,
    db: Session,
    api_key: str,
    parts_version: int = 1,
):
    def event(part):
        return f"data: {part.model_dump_json()}\n\n"

    response_stream = None
    try:
        _, references = transcript_context(transcript)
        messages = [
            {
                "role": "system",
                "content": build_system_instruction(
                    video_title, transcript, parts_version
                ),
            }
        ]
        for msg in history:
            content = msg["content"]
            if msg["role"] == DB_ROLE_ASSISTANT:
                parts = stored_parts(content, msg.get("metadata"))
                model_parts = history_parts(parts, references, parts_version)
                content = json.dumps({"parts": model_parts})
            messages.append({"role": msg["role"], "content": content})

        client = OpenAI(api_key=api_key, base_url=settings.openrouter_base_url)
        response_stream = client.chat.completions.create(
            model=settings.wiz_model,
            messages=messages,
            max_tokens=settings.wiz_max_tokens,
            stream=True,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "wiz_response",
                    "strict": True,
                    "schema": (
                        ModelResponseV2 if parts_version == 2 else ModelResponse
                    ).model_json_schema(),
                },
            },
            extra_body={"provider": {"require_parameters": True}},
        )
        decoder = PartsDecoder(parts_version)
        resolved = []
        blocks_in = blocks_split = 0
        referenced: set[str] = set()
        dropped: Counter = Counter()
        finish_reason = None
        for chunk in response_stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if getattr(choice, "finish_reason", None):
                finish_reason = choice.finish_reason
            delta = choice.delta
            if getattr(delta, "refusal", None):
                raise ValueError("Model refused structured response")
            if delta and delta.content:
                for part in decoder.feed(delta.content):
                    if isinstance(part, ModelBlock):
                        split = split_block(part)
                        blocks_in += 1
                        blocks_split += len(split.blocks) > 1
                        referenced.update(
                            key for ref in part.references for key in ref.chunk_ids
                        )
                        for drop in split.dropped:
                            dropped[drop.reason] += 1
                        emitted = [resolve_block(b, references) for b in split.blocks]
                    elif isinstance(part, ChunkReference):
                        reference = references.get(part.chunk_id)
                        if reference is None:
                            logger.warning(
                                "Omitting invalid Wiz reference",
                                extra={
                                    "chunk_id": part.chunk_id,
                                    "conversation_id": conversation_id,
                                },
                            )
                            continue
                        emitted = [reference]
                    else:
                        emitted = [part]
                    for item in emitted:
                        resolved.append(item)
                        yield event(item)
        if not decoder.buffer:
            yield event(
                ErrorEvent(message="No response from AI model. Please try again.")
            )
            return
        decoder.finish()
        if parts_version == 2:
            log_wiz_structure(
                blocks_in=blocks_in,
                blocks_split=blocks_split,
                referenced=referenced,
                resolved=resolved,
                dropped=dropped,
            )
        if finish_reason != "stop":
            raise ValueError("Incomplete model response")
        content = text_projection(resolved)
        if not content.strip():
            yield event(
                ErrorEvent(message="No response from AI model. Please try again.")
            )
            return
        message = save_chat_message(
            db,
            conversation_id,
            DB_ROLE_ASSISTANT,
            content,
            metadata={
                "parts_version": parts_version,
                "parts": [part.model_dump() for part in resolved],
            },
        )
        yield event(DoneEvent(message_id=message.id))
    except Exception:
        db.rollback()
        logger.exception(
            "Wiz structured response failed", extra={"conversation_id": conversation_id}
        )
        yield event(ErrorEvent(message="Processing error"))
    finally:
        if response_stream is not None and hasattr(response_stream, "close"):
            response_stream.close()


def ensure_openrouter_api_key() -> str:
    logger.debug("Ensuring OpenRouter API key configured")
    if not settings.openrouter_api_key:
        raise InternalServerError("OpenRouter API key not configured")
    return settings.openrouter_api_key


def prepare_chat(
    db: Session,
    conversation: Conversation,
    viewer: ViewerContext,
    message: str,
) -> tuple[Video | None, list | None, list[dict], str | None]:
    logger.debug(
        "Preparing chat",
        extra={"conversation_id": conversation.id, "user_id": viewer.user_id},
    )
    check_daily_quota(db, viewer.user_id, viewer.guest_session_id)

    transcript_result = get_valid_transcript_or_raise(db, conversation.video_id)
    if transcript_result is None:
        logger.debug(
            "Transcript processing", extra={"conversation_id": conversation.id}
        )
        return None, None, [], None

    video, transcript = transcript_result
    api_key = ensure_openrouter_api_key()

    save_chat_message(
        db,
        conversation.id,
        DB_ROLE_USER,
        message,
    )
    logger.debug("Saved user message", extra={"conversation_id": conversation.id})

    history_msgs = fetch_recent_history(db, conversation.id, limit=10)
    history_serializable = [
        {"role": msg.role, "content": msg.content, "metadata": msg.metadata_}
        for msg in history_msgs
    ]

    return video, transcript, history_serializable, api_key
