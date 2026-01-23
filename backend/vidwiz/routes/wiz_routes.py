from flask import Blueprint, request, jsonify
from vidwiz.shared.logging import get_logger
from vidwiz.shared.tasks import (
    create_transcript_task,
    create_metadata_task,
)
from vidwiz.shared.utils import push_video_to_summary_sqs, require_json_body
from vidwiz.shared.schemas import WizInitRequest, WizVideoStatusResponse
from vidwiz.shared.models import Video, Task, TaskStatus, db
from vidwiz.shared.errors import (
    handle_validation_error,
    NotFoundError,
    BadRequestError,
    UnauthorizedError,
    RateLimitError,
)
from vidwiz.shared.config import (
    FETCH_TRANSCRIPT_TASK_TYPE,
    FETCH_METADATA_TASK_TYPE,
)
from pydantic import ValidationError

logger = get_logger("vidwiz.routes.wiz_routes")

wiz_bp = Blueprint("wiz", __name__)


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
                {
                    "message": "Video created. All tasks queued.",
                    "video_id": video_id,
                    "is_new": True,
                }
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
            {
                "message": message,
                "video_id": video_id,
                "is_new": False,
                "tasks_queued": tasks_queued,
            }
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


@wiz_bp.route("/wiz/chat", methods=["POST"])
@require_json_body
def chat_wiz():
    """
    Chat with the Wiz for a specific video.
    Supports authenticated users (JWT) and guest users (guest_session_id).
    Enforces quotas: 20/day for users, 5/day for guests.
    Streams response using SSE.
    """
    from vidwiz.shared.models import Conversation, Message, User, db
    from vidwiz.shared.utils import get_transcript_from_s3
    from vidwiz.shared.config import FETCH_TRANSCRIPT_TASK_TYPE
    import jwt
    from flask import Response, stream_with_context, current_app
    import requests
    import os
    import json
    from datetime import datetime, timezone

    # 1. Authentication & Identity Resolution
    user_id = None
    guest_session_id = None

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(
                token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
            )
            user_id = payload["user_id"]
        except Exception as e:
            logger.error(f"JWT Decode Error: {e}")
            pass  # Invalid token, treat as guest if session id present? Or fail?

    if not user_id:
        # Check for guest session id
        guest_session_id = request.headers.get("X-Guest-Session-ID")
        if not guest_session_id:
            raise UnauthorizedError("Missing Auth or Guest ID")

    # 2. Input Validation
    if "video_id" not in request.json_data or "message" not in request.json_data:
        raise BadRequestError("Missing video_id or message")

    video_id = request.json_data["video_id"]
    user_message = request.json_data["message"]

    # 3. Quota Check
    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    if user_id:
        # Check user quota
        msg_count = (
            Message.query.join(Conversation)
            .filter(
                Conversation.user_id == user_id,
                Message.role == "user",
                Message.created_at >= today,
            )
            .count()
        )
        if msg_count >= 20:
            raise RateLimitError("Daily limit reached (20 messages/day)")
    else:
        # Check guest quota
        msg_count = (
            Message.query.join(Conversation)
            .filter(
                Conversation.guest_session_id == guest_session_id,
                Message.role == "user",
                Message.created_at >= today,
            )
            .count()
        )
        if msg_count >= 5:
            raise RateLimitError("Daily guest limit reached (5 messages/day)")

    # 4. Transcript Gating
    video = Video.query.filter_by(video_id=video_id).first()
    if not video:
        raise NotFoundError("Video not found")

    # Check transcript availability (DB flag primary, S3 fallback if needed, but DB should be sync)
    if not video.transcript_available:
        # If task is still running
        if has_active_task(video_id, FETCH_TRANSCRIPT_TASK_TYPE):
            return jsonify({"status": "processing", "message": "Transcript processing"}), 202
        raise BadRequestError("Transcript unavailable. Please init session first.")

    transcript = get_transcript_from_s3(video_id)
    if not transcript:
        # Should not happen if video.transcript_available is True, but good safety
        raise NotFoundError("Transcript data missing")

    # 5. Conversation Context
    # Find or create conversation
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

    # Save User Message
    new_message = Message(
        conversation_id=conversation.id, role="user", content=user_message
    )
    db.session.add(new_message)
    db.session.commit()

    # 6. Prepare LLM Context
    # Fetch recent history
    history = (
        Message.query.filter_by(conversation_id=conversation.id)
        .order_by(Message.created_at.desc())
        .limit(10)
        .all()
    )
    history.reverse()  # Oldest first

    # Construct Prompt
    # Simplify transcript content for context (truncating if too large? For now assume it fits or use RAG later)
    # Current "Wiz" instruction says: strictly limited to the video transcript.
    # We will dump the transcript text.
    transcript_text = "\n".join(
        [f"{int(s['offset'] // 60)}:{int(s['offset'] % 60):02d} {s['text']}" for s in transcript]
    )

    system_prompt = f"""You are Wiz, an AI assistant dedicated to this specific video: "{video.title}".
Your context is strictly limited to the provided video transcript.
Answer the user's question based ONLY on the transcript.
If the answer is not in the transcript, say so.
Use inline timestamp citations like [mm:ss] when referencing specific parts.
Transcript:
{transcript_text}
"""

    messages_payload = [{"role": "user", "parts": [{"text": system_prompt}]}]
    # Add history
    for msg in history:
        # Skip the system prompt we just added (or rather, the message we just saved is in history)
        # We need to map role: 'assistant' -> 'model'
        role = "model" if msg.role == "assistant" else "user"
        # Avoid duplicating the very last user message which we already have in 'history' DB fetch?
        # Yes, 'history' includes 'new_message'.
        # But we constructed system prompt as the FIRST user message context.
        # So we should probably treat system prompt as context, and then append history.
        # But Gemini API often expects system instruction separate or just a long context.
        # Let's just append history.
        messages_payload.append({"role": role, "parts": [{"text": msg.content}]})

    # Remove the last message from payload if it duplicates what we want to send?
    # Actually, we can just send the whole history.
    # Wait, 'system_prompt' is huge. We should make it the first part of the request.

    # Refined payload strategy:
    gemini_payload = {
        "contents": messages_payload,
        "generationConfig": {"maxOutputTokens": 1000},
    }

    GEN_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEN_API_KEY:
        logger.error("GEMINI_API_KEY not set")
        return jsonify({"error": "Server configuration error"}), 500

    def generate():
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:streamGenerateContent?key={GEN_API_KEY}&alt=sse"
        headers = {"Content-Type": "application/json"}
        
        full_response_text = ""
        
        try:
            with requests.post(url, json=gemini_payload, headers=headers, stream=True) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        
                        # Gemini SSE format with alt=sse: "data: {json}"
                        if decoded_line.startswith('data: '):
                            json_str = decoded_line[6:]  # Strip 'data: '
                            try:
                                chunk_data = json.loads(json_str)
                                # Extract text from chunk
                                if "candidates" in chunk_data and chunk_data["candidates"]:
                                    cand = chunk_data["candidates"][0]
                                    if "content" in cand and "parts" in cand["content"]:
                                        for part in cand["content"]["parts"]:
                                            if "text" in part:
                                                text_chunk = part["text"]
                                                full_response_text += text_chunk
                                                yield f"data: {json.dumps({'content': text_chunk})}\n\n"
                            except json.JSONDecodeError as parse_err:
                                logger.warning(f"JSON parse error: {parse_err}")
                                pass
        except Exception as e:
            logger.error(f"Gemini stream error: {e}")
            yield f"data: {json.dumps({'error': 'Stream error'})}\n\n"
        
        # Save complete assistant message
        if full_response_text:
             with current_app.app_context():
                bot_msg = Message(
                    conversation_id=conversation.id,
                    role="assistant",
                    content=full_response_text
                )
                db.session.add(bot_msg)
                db.session.commit()
        
        yield "data: [DONE]\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")
