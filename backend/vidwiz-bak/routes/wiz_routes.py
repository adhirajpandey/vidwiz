from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context
from pydantic import ValidationError

from vidwiz.shared.errors import (
    InternalServerError,
    NotFoundError,
    handle_validation_error,
)
from vidwiz.shared.logging import get_logger
from vidwiz.shared.schemas import (
    WizChatRequest,
    WizConversationCreateRequest,
    WizConversationResponse,
    WizInitRequest,
    WizInitResponse,
    WizVideoStatusResponse,
)
from vidwiz.shared.utils import (
    jwt_or_guest_required,
    require_json_body,
)
from vidwiz.services.wiz_service import (
    DB_ROLE_USER,
    check_daily_quota,
    create_conversation,
    fetch_recent_history,
    fetch_video,
    get_conversation_for_identity,
    get_valid_transcript_or_raise,
    init_wiz_session as init_wiz_session_service,
    save_chat_message,
    stream_wiz_response,
)

logger = get_logger("vidwiz.routes.wiz_routes")

wiz_bp = Blueprint("wiz", __name__)


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

    video, message, is_new, tasks_queued = init_wiz_session_service(video_id)
    return (
        jsonify(
            WizInitResponse(
                message=message,
                video_id=video_id,
                is_new=is_new,
                tasks_queued=tasks_queued,
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
    video = fetch_video(video_id)
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


@wiz_bp.route("/wiz/conversation", methods=["POST"])
@jwt_or_guest_required
@require_json_body
def create_wiz_conversation():
    """
    Create a new Wiz conversation for a video.
    """
    user_id = request.user_id
    guest_session_id = request.guest_session_id

    try:
        convo_request = WizConversationCreateRequest.model_validate(request.json_data)
    except ValidationError as e:
        logger.warning(f"Wiz conversation validation error: {e}")
        return handle_validation_error(e)

    video = fetch_video(convo_request.video_id)
    if not video:
        raise NotFoundError("Video not found")

    conversation = create_conversation(
        convo_request.video_id, user_id, guest_session_id
    )

    return (
        jsonify(
            WizConversationResponse(
                conversation_id=conversation.id, video_id=conversation.video_id
            ).model_dump()
        ),
        200,
    )


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

    api_key = current_app.config.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not set in app config")
        raise InternalServerError("Gemini API key not configured")

    video_id = chat_data.video_id
    user_message = chat_data.message
    conversation_id = chat_data.conversation_id

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
    if conversation_id:
        conversation = get_conversation_for_identity(
            conversation_id, video_id, user_id, guest_session_id
        )
    else:
        conversation = create_conversation(video_id, user_id, guest_session_id)

    # Save User Message
    save_chat_message(conversation.id, DB_ROLE_USER, user_message)

    history_msgs = fetch_recent_history(conversation.id, limit=10)

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
                api_key=api_key,
            )
        ),
        mimetype="text/event-stream",
    )
