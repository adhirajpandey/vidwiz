import json
import logging
from datetime import datetime, timedelta

import boto3
from openai import OpenAI
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.auth.schemas import ViewerContext
from src.conversations.config import conversations_settings
from src.conversations.models import Conversation, Message
from src.exceptions import InternalServerError, RateLimitError, NotFoundError
from src.internal.scheduling import schedule_video_tasks
from src.videos.models import Video
from src.videos import service as videos_service

DB_ROLE_USER = "user"
DB_ROLE_ASSISTANT = "assistant"

logger = logging.getLogger(__name__)


def get_or_create_video(db: Session, video_id: str) -> tuple[Video, bool]:
    video = videos_service.get_video_by_id(db, video_id)
    if video:
        schedule_video_tasks(db, video)
        return video, False

    video = Video(video_id=video_id)
    db.add(video)
    db.commit()
    db.refresh(video)

    schedule_video_tasks(db, video)

    return video, True


def create_conversation(
    db: Session, video_id: str, user_id: int | None, guest_session_id: str | None
) -> Conversation:
    conversation = Conversation(
        video_id=video_id,
        user_id=user_id,
        guest_session_id=guest_session_id,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def get_conversation_for_viewer(
    db: Session, conversation_id: int, viewer: ViewerContext
) -> Conversation | None:
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
    message = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        metadata_=metadata,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def fetch_recent_history(
    db: Session, conversation_id: int, limit: int = 10
) -> list[Message]:
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
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    query = (
        select(func.count())
        .select_from(Message)
        .join(Conversation)
        .where(Message.role == DB_ROLE_USER, Message.created_at >= today)
    )

    if user_id:
        query = query.where(Conversation.user_id == user_id)
        limit = conversations_settings.wiz_user_daily_quota
        limit_msg_suffix = "messages/day"
    elif guest_session_id:
        query = query.where(Conversation.guest_session_id == guest_session_id)
        limit = conversations_settings.wiz_guest_daily_quota
        limit_msg_suffix = "guest messages/day"
    else:
        return

    msg_count = db.execute(query).scalar_one()
    if msg_count >= limit:
        tomorrow_midnight = today + timedelta(days=1)
        now = datetime.utcnow()
        seconds_until_reset = int((tomorrow_midnight - now).total_seconds())
        raise RateLimitError(
            f"Daily limit reached ({limit} {limit_msg_suffix})",
            details={"reset_in_seconds": seconds_until_reset},
        )


def get_transcript_from_s3(video_id: str) -> list | None:
    if not conversations_settings.s3_bucket_name:
        return None
    if not (
        conversations_settings.aws_access_key_id
        and conversations_settings.aws_secret_access_key
        and conversations_settings.aws_region
    ):
        return None

    transcript_key = f"transcripts/{video_id}.json"
    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=conversations_settings.aws_access_key_id,
            aws_secret_access_key=conversations_settings.aws_secret_access_key,
            region_name=conversations_settings.aws_region,
        )
        response = s3_client.get_object(
            Bucket=conversations_settings.s3_bucket_name, Key=transcript_key
        )
        transcript_data = json.loads(response["Body"].read().decode("utf-8"))
        return transcript_data
    except Exception as exc:
        logger.warning("Transcript fetch failed", extra={"error": str(exc)})
        return None


def get_valid_transcript_or_raise(
    db: Session, video_id: str
) -> tuple[Video, list] | None:
    video = videos_service.get_video_by_id(db, video_id)
    if not video:
        raise NotFoundError("Video not found")

    if not video.transcript_available:
        return None

    transcript = get_transcript_from_s3(video_id)
    if not transcript:
        raise NotFoundError("Transcript data missing")

    return video, transcript


def _format_mm_ss(seconds: float) -> str:
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes}:{secs:02d}"


def build_transcript_text(transcript: list, *, include_timestamps: bool = True) -> str:
    lines = []
    for segment in transcript:
        if "text" not in segment:
            continue
        text = segment["text"]
        if include_timestamps and "offset" in segment:
            lines.append(f"{_format_mm_ss(float(segment['offset']))} {text}")
        else:
            lines.append(text)
    return "\n".join(lines) if include_timestamps else " ".join(lines)


def build_system_instruction(video_title: str | None, transcript: list) -> str:
    transcript_text = build_transcript_text(transcript, include_timestamps=True)

    title = video_title or "this video"
    safe_title = title.replace("{", "{{").replace("}", "}}")
    safe_transcript = transcript_text.replace("{", "{{").replace("}", "}}")

    return conversations_settings.wiz_system_prompt_template.format(
        title=safe_title,
        transcript=safe_transcript,
    )


def stream_wiz_response(
    *,
    video_title: str | None,
    transcript: list,
    history: list[dict],
    conversation_id: int,
    db: Session,
    api_key: str,
):
    system_instruction = build_system_instruction(video_title, transcript)

    client = OpenAI(
        api_key=api_key,
        base_url=conversations_settings.openrouter_base_url,
    )

    messages: list[dict] = [{"role": "system", "content": system_instruction}]
    for msg in history:
        role = "assistant" if msg["role"] == DB_ROLE_ASSISTANT else "user"
        messages.append({"role": role, "content": msg["content"]})

    try:
        full_response_text = ""

        response_stream = client.chat.completions.create(
            model=conversations_settings.openrouter_model_name,
            messages=messages,
            max_tokens=1000,
            stream=True,
        )

        for chunk in response_stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                full_response_text += delta.content
                yield f"data: {json.dumps({'content': delta.content})}\n\n"

        if full_response_text:
            save_chat_message(
                db, conversation_id, DB_ROLE_ASSISTANT, full_response_text
            )

        yield "data: [DONE]\n\n"

    except Exception as exc:
        logger.error("OpenRouter streaming error", extra={"error": str(exc)})
        yield f"data: {json.dumps({'error': 'Processing error'})}\n\n"


def ensure_openrouter_api_key() -> str:
    if not conversations_settings.openrouter_api_key:
        raise InternalServerError("OpenRouter API key not configured")
    return conversations_settings.openrouter_api_key


def prepare_chat(
    db: Session,
    conversation: Conversation,
    viewer: ViewerContext,
    message: str,
) -> tuple[Video | None, list | None, list[dict], str | None]:
    check_daily_quota(db, viewer.user_id, viewer.guest_session_id)

    transcript_result = get_valid_transcript_or_raise(db, conversation.video_id)
    if transcript_result is None:
        return None, None, [], None

    video, transcript = transcript_result
    api_key = ensure_openrouter_api_key()

    save_chat_message(
        db,
        conversation.id,
        DB_ROLE_USER,
        message,
    )

    history_msgs = fetch_recent_history(db, conversation.id, limit=10)
    history_serializable = [
        {"role": msg.role, "content": msg.content} for msg in history_msgs
    ]

    return video, transcript, history_serializable, api_key
