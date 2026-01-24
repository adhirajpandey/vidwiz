import json
import os
from datetime import datetime, timezone

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from google import genai
from google.genai import types
from pydantic import ValidationError

from vidwiz.shared.config import (
    FETCH_METADATA_TASK_TYPE,
    FETCH_TRANSCRIPT_TASK_TYPE,
    GEMINI_MODEL_NAME,
    WIZ_GUEST_DAILY_QUOTA,
    WIZ_USER_DAILY_QUOTA,
)
from vidwiz.shared.errors import (
    BadRequestError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
    handle_validation_error,
)
from vidwiz.shared.logging import get_logger
from vidwiz.shared.models import Conversation, Message, Task, TaskStatus, User, Video, db
from vidwiz.shared.schemas import (
    WizChatProcessingResponse,
    WizChatRequest,
    WizInitRequest,
    WizInitResponse,
    WizVideoStatusResponse,
)
from vidwiz.shared.tasks import create_metadata_task, create_transcript_task
from vidwiz.shared.utils import (
    get_transcript_from_s3,
    jwt_or_guest_required,
    push_video_to_summary_sqs,
    require_json_body,
)

logger = get_logger("vidwiz.routes.wiz_routes")

wiz_bp = Blueprint("wiz", __name__)


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
        # Should be unreachable due to decorators
        return

    msg_count = query.count()
    if msg_count >= limit:
        raise RateLimitError(f"Daily limit reached ({limit} {limit_msg_suffix})")



def has_active_task(video_id: str, task_type: str) -> bool:
    """Check if there's a pending, in-progress, or completed task for the given video and task type."""
    active_statuses = [TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.COMPLETED]
    task = Task.query.filter(
        Task.task_type == task_type,
        Task.task_details["video_id"].as_string() == video_id,
        Task.status.in_(active_statuses),
    ).first()
    return task is not None


@wiz_bp.route("/wiz/init", methods=["POST"])
@require_json_body
def init_wiz_session():
    """
    Initialize a wiz session for a video.
    This triggers background tasks for transcript, metadata, and summary generation.
    """
    try:
        wiz_request = WizInitRequest.model_validate(request.json_data)
    except ValidationError as e:
        logger.warning(f"Wiz init validation error: {e}")
        return handle_validation_error(e)

    video_id = wiz_request.video_id
    logger.info(f"Initializing wiz session for video_id={video_id}")

    # Check if video exists
    video = Video.query.filter_by(video_id=video_id).first()

    if not video:
        # Create new video and queue all tasks
        logger.info(f"Creating new video for video_id={video_id}")
        video = Video(video_id=video_id)
        db.session.add(video)
        db.session.commit()

        create_transcript_task(video_id)
        create_metadata_task(video_id)
        push_video_to_summary_sqs(video_id)

        return (
            jsonify(
                WizInitResponse(
                    message="Video created. All tasks queued.",
                    video_id=video_id,
                    is_new=True,
                ).model_dump()
            ),
            200,
        )

    # Video exists, check each task condition
    tasks_queued = []

    # Transcript: if not available and no active task
    if not video.transcript_available and not has_active_task(video_id, FETCH_TRANSCRIPT_TASK_TYPE):
        create_transcript_task(video_id)
        tasks_queued.append("transcript")

    # Metadata: if video_metadata is null and no active task
    if video.video_metadata is None and not has_active_task(video_id, FETCH_METADATA_TASK_TYPE):
        create_metadata_task(video_id)
        tasks_queued.append("metadata")

    # Summary: if summary is null, push to SQS for generation
    if video.summary is None:
        push_video_to_summary_sqs(video_id)
        tasks_queued.append("summary")

    message = f"Tasks queued: {', '.join(tasks_queued)}" if tasks_queued else "No new tasks needed."

    return (
        jsonify(
            WizInitResponse(
                message=message,
                video_id=video_id,
                is_new=False,
                tasks_queued=tasks_queued if tasks_queued else None,
            ).model_dump()
        ),
        200,
    )


@wiz_bp.route("/wiz/video/<video_id>", methods=["GET"])
def get_wiz_video_status(video_id):
    """
    Get video status for wiz workspace.
    Returns transcript_available, metadata, and summary status.
    No authentication required for wiz feature.
    """
    video = Video.query.filter_by(video_id=video_id).first()
    if not video:
        logger.warning(f"Wiz video not found video_id={video_id}")
        raise NotFoundError("Video not found")

    response_data = WizVideoStatusResponse(
        video_id=video.video_id,
        title=video.title,
        transcript_available=video.transcript_available,
        metadata=video.video_metadata,
        summary=video.summary,
    )

    logger.info(f"Fetched wiz video status for video_id={video_id}")
    return jsonify(response_data.model_dump()), 200



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


def get_or_create_conversation(video_id: str, user_id: int | None, guest_session_id: str | None) -> Conversation:
    """
    Find or create a conversation for the user/guest and video.
    """
    if user_id:
        conversation = Conversation.query.filter_by(
            video_id=video_id, user_id=user_id
        ).first()
    else:
        conversation = Conversation.query.filter_by(
            video_id=video_id, guest_session_id=guest_session_id
        ).first()

    if not conversation:
        conversation = Conversation(
            video_id=video_id, user_id=user_id, guest_session_id=guest_session_id
        )
        db.session.add(conversation)
        db.session.commit()
    
    return conversation


def save_chat_message(conversation_id: int, role: str, content: str) -> Message:
    """
    Save a message to the database.
    """
    message = Message(
        conversation_id=conversation_id, role=role, content=content
    )
    db.session.add(message)
    db.session.commit()
    return message


def build_system_instruction(video_title: str, transcript: list) -> str:
    """
    Construct the system instruction prompt using the transcript.
    """
    transcript_text = "\n".join(
        [
            f"{int(s['offset'] // 60)}:{int(s['offset'] % 60):02d} {s['text']}"
            for s in transcript
        ]
    )

    return f"""You are Wiz, an AI assistant dedicated to this specific video: "{video_title}".
Your context is strictly limited to the provided video transcript.
Answer the user's question based ONLY on the transcript.
If the answer is not in the transcript, say so.
Use inline timestamp citations like [mm:ss] when referencing specific parts.
Transcript:
{transcript_text}
"""




def stream_wiz_response(
    video_title: str,
    transcript: list,
    history: list[dict],
    conversation_id: int,
    app,
):
    """
    Generator function to stream response from Gemini and save the assistant message.
    """
    api_key = current_app.config.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not set in app config")
        # We can't raise HTTP error easily here as streaming started, 
        # but we can yield an error message or just log and finish.
        # However, checking it before calling this is better practice for the route.
        # But since we are moving logic here, let's assume valid key or fail.
        yield f"data: {json.dumps({'error': 'Configuration error'})}\n\n"
        return

    system_instruction = build_system_instruction(video_title, transcript)
    
    client = genai.Client(api_key=api_key)

    # Build history for SDK
    gemini_history = []
    # All messages except the last one are history
    # The last message is the current user message
    history_to_process = history[:-1]
    user_message_content = history[-1]["content"]

    for msg in history_to_process:
        role = GEMINI_ROLE_MODEL if msg["role"] == DB_ROLE_ASSISTANT else GEMINI_ROLE_USER
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

        # Save complete assistant message
        if full_response_text:
            with app.app_context():
                save_chat_message(
                    conversation_id, DB_ROLE_ASSISTANT, full_response_text
                )

        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Gemini SDK error: {e}")
        yield f"data: {json.dumps({'error': 'Processing error'})}\n\n"


@wiz_bp.route("/wiz/chat", methods=["POST"])
@jwt_or_guest_required
@require_json_body
def chat_wiz():
    """
    Chat with the Wiz for a specific video.
    Supports authenticated users (JWT) and guest users (guest_session_id).
    Enforces quotas: 20/day for users, 5/day for guests.
    Streams response using SSE.
    """
    # 1. Identity Resolution (Handled by decorator)
    user_id = request.user_id
    guest_session_id = request.guest_session_id

    # 2. Input Validation
    try:
        chat_data = WizChatRequest.model_validate(request.json_data)
    except ValidationError as e:
        logger.warning(f"Wiz chat validation error: {e}")
        return handle_validation_error(e)

    video_id = chat_data.video_id
    user_message = chat_data.message

    # 3. Quota Check
    check_daily_quota(user_id, guest_session_id)

    # 4. Transcript Gating
    result = get_valid_transcript_or_raise(video_id)
    # Handle the tuple return which might include a Response object (for 202 processing)
    if (
        isinstance(result, tuple)
        and len(result) == 2
        and isinstance(result[0], Response)
    ):
        # This is likely the (response, status_code) tuple from processing state
        return result

    video, transcript = result

    # 5. Conversation Context
    conversation = get_or_create_conversation(video_id, user_id, guest_session_id)

    # Save User Message
    new_message = save_chat_message(conversation.id, DB_ROLE_USER, user_message)

    # 6. Prepare LLM Context
    # Fetch recent history
    history_msgs = (
        Message.query.filter_by(conversation_id=conversation.id)
        .order_by(Message.created_at.desc())
        .limit(10)
        .all()
    )
    history_msgs.reverse()  # Oldest first


    # Prepare prompt data (extract from models before streaming)
    video_title = video.title
    history_serializable = [
        {"role": msg.role, "content": msg.content}
        for msg in history_msgs
    ]

    # App context for generator
    app = current_app._get_current_object()

    return Response(
        stream_with_context(
            stream_wiz_response(
                video_title=video_title,
                transcript=transcript,
                history=history_serializable,
                conversation_id=conversation.id,
                app=app,
            )
        ),
        mimetype="text/event-stream",
    )




