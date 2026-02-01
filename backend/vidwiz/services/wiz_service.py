import json
from datetime import datetime, timezone, timedelta

from flask import Response, jsonify, stream_with_context
from google import genai
from google.genai import types

from vidwiz.shared.config import (
    FETCH_METADATA_TASK_TYPE,
    FETCH_TRANSCRIPT_TASK_TYPE,
    GEMINI_MODEL_NAME,
    WIZ_GUEST_DAILY_QUOTA,
    WIZ_USER_DAILY_QUOTA,
)
from vidwiz.shared.errors import BadRequestError, NotFoundError, RateLimitError
from vidwiz.shared.logging import get_logger
from vidwiz.shared.models import Conversation, Message, Task, TaskStatus, Video, db
from vidwiz.shared.schemas import WizChatProcessingResponse
from vidwiz.shared.tasks import create_metadata_task, create_transcript_task
from vidwiz.shared.utils import get_transcript_from_s3, push_video_to_summary_sqs

logger = get_logger("vidwiz.services.wiz_service")

# Constants for Roles
GEMINI_ROLE_USER = "user"
GEMINI_ROLE_MODEL = "model"
DB_ROLE_ASSISTANT = "assistant"
DB_ROLE_USER = "user"


def check_daily_quota(user_id: int | None, guest_session_id: str | None):
    """
    Check if the user or guest has exceeded their daily message quota.
    Raises RateLimitError if quota is exceeded.
    """
    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    query = Message.query.join(Conversation).filter(
        Message.role == DB_ROLE_USER, Message.created_at >= today
    )

    if user_id:
        query = query.filter(Conversation.user_id == user_id)
        limit = WIZ_USER_DAILY_QUOTA
        limit_msg_suffix = "messages/day"
    elif guest_session_id:
        query = query.filter(Conversation.guest_session_id == guest_session_id)
        limit = WIZ_GUEST_DAILY_QUOTA
        limit_msg_suffix = "guest messages/day"
    else:
        return

    msg_count = query.count()
    if msg_count >= limit:
        tomorrow_midnight = today + timedelta(days=1)
        now = datetime.now(timezone.utc)

        seconds_until_reset = int((tomorrow_midnight - now).total_seconds())

        raise RateLimitError(
            f"Daily limit reached ({limit} {limit_msg_suffix})",
            details={"reset_in_seconds": seconds_until_reset},
        )



def has_active_task(video_id: str, task_type: str) -> bool:
    """Check if there's a pending, in-progress, or completed task for the given video and task type."""
    active_statuses = [
        TaskStatus.PENDING,
        TaskStatus.IN_PROGRESS,
        TaskStatus.COMPLETED,
    ]
    task = Task.query.filter(
        Task.task_type == task_type,
        Task.task_details["video_id"].as_string() == video_id,
        Task.status.in_(active_statuses),
    ).first()
    return task is not None



def init_wiz_session(video_id: str):
    """
    Ensure a video exists and queue transcript/metadata/summary tasks as needed.
    Returns (video, message, is_new, tasks_queued).
    """
    video = Video.query.filter_by(video_id=video_id).first()

    if not video:
        video = Video(video_id=video_id)
        db.session.add(video)
        db.session.commit()

        create_transcript_task(video_id)
        create_metadata_task(video_id)
        push_video_to_summary_sqs(video_id)

        return video, "Video created. All tasks queued.", True, None

    tasks_queued = []

    if not video.transcript_available and not has_active_task(
        video_id, FETCH_TRANSCRIPT_TASK_TYPE
    ):
        create_transcript_task(video_id)
        tasks_queued.append("transcript")

    if video.video_metadata is None and not has_active_task(
        video_id, FETCH_METADATA_TASK_TYPE
    ):
        create_metadata_task(video_id)
        tasks_queued.append("metadata")

    if video.summary is None:
        push_video_to_summary_sqs(video_id)
        tasks_queued.append("summary")

    message = (
        f"Tasks queued: {', '.join(tasks_queued)}"
        if tasks_queued
        else "No new tasks needed."
    )

    return video, message, False, tasks_queued if tasks_queued else None



def fetch_video(video_id: str):
    return Video.query.filter_by(video_id=video_id).first()



def get_valid_transcript_or_raise(video_id: str):
    """
    Validate video existence, transcript availability, and fetch transcript from S3.
    """
    video = Video.query.filter_by(video_id=video_id).first()
    if not video:
        raise NotFoundError("Video not found")

    if not video.transcript_available:
        if has_active_task(video_id, FETCH_TRANSCRIPT_TASK_TYPE):
            return (
                jsonify(
                    WizChatProcessingResponse(
                        status="processing", message="Transcript processing"
                    ).model_dump()
                ),
                202,
            )
        raise BadRequestError("Transcript unavailable. Please init session first.")

    transcript = get_transcript_from_s3(video_id)
    if not transcript:
        raise NotFoundError("Transcript data missing")

    return video, transcript



def create_conversation(
    video_id: str, user_id: int | None, guest_session_id: str | None
) -> Conversation:
    conversation = Conversation(
        video_id=video_id, user_id=user_id, guest_session_id=guest_session_id
    )
    db.session.add(conversation)
    db.session.commit()
    return conversation



def get_conversation_for_identity(
    conversation_id: int,
    video_id: str,
    user_id: int | None,
    guest_session_id: str | None,
) -> Conversation:
    if user_id:
        conversation = Conversation.query.filter_by(
            id=conversation_id, video_id=video_id, user_id=user_id
        ).first()
    else:
        conversation = Conversation.query.filter_by(
            id=conversation_id,
            video_id=video_id,
            guest_session_id=guest_session_id,
        ).first()

    if not conversation:
        raise NotFoundError("Conversation not found")

    return conversation



def save_chat_message(conversation_id: int, role: str, content: str) -> Message:
    message = Message(
        conversation_id=conversation_id, role=role, content=content
    )
    db.session.add(message)
    db.session.commit()
    return message



def build_system_instruction(video_title: str, transcript: list) -> str:
    transcript_text = "\n".join(
        [
            f"{int(s['offset'] // 60)}:{int(s['offset'] % 60):02d} {s['text']}"
            for s in transcript
        ]
    )

    return f"""You are Wiz, an AI assistant dedicated to this specific video: \"{video_title}\".
Your context is strictly limited to the provided video transcript.
Answer the user's question based ONLY on the transcript.
If the answer is not in the transcript, say so.
Use inline timestamp citations like [mm:ss] when referencing specific parts.
Transcript:
{transcript_text}
"""



def fetch_recent_history(conversation_id: int, limit: int = 10):
    history_msgs = (
        Message.query.filter_by(conversation_id=conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
    history_msgs.reverse()
    return history_msgs



def stream_wiz_response(
    video_title: str,
    transcript: list,
    history: list[dict],
    conversation_id: int,
    app,
    api_key: str,
):
    system_instruction = build_system_instruction(video_title, transcript)

    client = genai.Client(api_key=api_key)

    gemini_history = []
    history_to_process = history[:-1]
    user_message_content = history[-1]["content"]

    for msg in history_to_process:
        role = (
            GEMINI_ROLE_MODEL
            if msg["role"] == DB_ROLE_ASSISTANT
            else GEMINI_ROLE_USER
        )
        gemini_history.append(
            types.Content(role=role, parts=[types.Part(text=msg["content"])])
        )

    try:
        chat = client.chats.create(
            model=GEMINI_MODEL_NAME,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction, max_output_tokens=1000
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
            with app.app_context():
                save_chat_message(
                    conversation_id, DB_ROLE_ASSISTANT, full_response_text
                )

        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Gemini SDK error: {e}")
        yield f"data: {json.dumps({'error': 'Processing error'})}\n\n"


