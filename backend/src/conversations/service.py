import json
import logging
from datetime import datetime, timedelta

import boto3
from google import genai
from google.genai import types
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.auth.schemas import ViewerContext
from src.conversations.config import conversations_settings
from src.conversations.models import Conversation, Message
from src.exceptions import InternalServerError, RateLimitError, NotFoundError
from src.internal import constants as internal_constants
from src.internal import service as internal_service
from src.videos.models import Video
from src.videos import service as videos_service

DB_ROLE_USER = "user"
DB_ROLE_ASSISTANT = "assistant"
GEMINI_ROLE_USER = "user"
GEMINI_ROLE_MODEL = "model"

logger = logging.getLogger(__name__)

def get_or_create_video(db: Session, video_id: str) -> tuple[Video, bool]:
    video = videos_service.get_video_by_id(db, video_id)
    if video:
        if not video.video_metadata:
            internal_service.create_task_idempotent(
                db, internal_constants.FETCH_METADATA_TASK_TYPE, video_id
            )
        if not video.transcript_available:
            internal_service.create_task_idempotent(
                db, internal_constants.FETCH_TRANSCRIPT_TASK_TYPE, video_id
            )
        return video, False

    video = Video(video_id=video_id)
    db.add(video)
    db.commit()
    db.refresh(video)

    # Schedule initial tasks
    internal_service.create_task_idempotent(
        db, internal_constants.FETCH_METADATA_TASK_TYPE, video_id
    )
    internal_service.create_task_idempotent(
        db, internal_constants.FETCH_TRANSCRIPT_TASK_TYPE, video_id
    )

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


def get_valid_transcript_or_raise(db: Session, video_id: str) -> tuple[Video, list] | None:
    video = videos_service.get_video_by_id(db, video_id)
    if not video:
        raise NotFoundError("Video not found")

    if not video.transcript_available:
        return None

    transcript = get_transcript_from_s3(video_id)
    if not transcript:
        raise NotFoundError("Transcript data missing")

    return video, transcript


def build_system_instruction(video_title: str | None, transcript: list) -> str:
    transcript_text = "\n".join(
        [
            f"{int(segment['offset'] // 60)}:{int(segment['offset'] % 60):02d} {segment['text']}"
            for segment in transcript
            if "offset" in segment and "text" in segment
        ]
    )

    title = video_title or "this video"

    return (
        "You are Wiz, an AI assistant dedicated to this specific video: "
        f'"{title}".\n'
        "Your context is strictly limited to the provided video transcript.\n"
        "Answer the user's question based ONLY on the transcript.\n"
        "If the answer is not in the transcript, say so.\n"
        "Use inline timestamp citations like [mm:ss] when referencing specific parts.\n"
        "Transcript:\n"
        f"{transcript_text}\n"
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

    client = genai.Client(api_key=api_key)

    gemini_history = []
    history_to_process = history[:-1]
    user_message_content = history[-1]["content"]

    for msg in history_to_process:
        role = GEMINI_ROLE_MODEL if msg["role"] == DB_ROLE_ASSISTANT else GEMINI_ROLE_USER
        gemini_history.append(
            types.Content(role=role, parts=[types.Part(text=msg["content"])])
        )

    try:
        chat = client.chats.create(
            model=conversations_settings.gemini_model_name,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=1000,
            ),
            history=gemini_history,
        )

        response_stream = chat.send_message_stream(user_message_content)
        full_response_text = ""

        for chunk in response_stream:
            if chunk.text:
                full_response_text += chunk.text
                yield f"data: {json.dumps({'content': chunk.text})}\n\n"

        if full_response_text:
            save_chat_message(
                db, conversation_id, DB_ROLE_ASSISTANT, full_response_text
            )

        yield "data: [DONE]\n\n"

    except Exception as exc:
        logger.error("Gemini SDK error", extra={"error": str(exc)})
        yield f"data: {json.dumps({'error': 'Processing error'})}\n\n"


def ensure_gemini_api_key() -> str:
    if not conversations_settings.gemini_api_key:
        raise InternalServerError("Gemini API key not configured")
    return conversations_settings.gemini_api_key


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
    api_key = ensure_gemini_api_key()

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
