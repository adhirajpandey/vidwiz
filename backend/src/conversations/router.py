from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user_id, get_viewer_context
from src.auth.schemas import ViewerContext
from src.config import settings
from src.conversations import service as conversations_service
from src.conversations.dependencies import get_conversation_or_404
from src.conversations.schemas import (
    ChatProcessingResponse,
    ConversationCreate,
    ConversationList,
    ConversationRead,
    MessageCreate,
    MessageRead,
)
from src.conversations.models import ConversationScope
from src.credits import service as credits_service
from src.exceptions import BadRequestError, UnauthorizedError
from src.videos.utils import normalize_youtube_video_id
from src.internal.scheduling import prepare_video
from src.database import get_db
from src.shared.ratelimit import limiter


router = APIRouter(prefix="/v2/conversations", tags=["Conversations"])


@router.post(
    "",
    response_model=ConversationRead,
    status_code=status.HTTP_201_CREATED,
    description="Start a conversation for a video; implicitly creates the video.",
)
def create_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    viewer: ViewerContext = Depends(get_viewer_context),
) -> ConversationRead:
    if payload.scope == ConversationScope.LIBRARY:
        # Library Ask is free within the daily message quota, for signed-in users.
        if not viewer.user_id:
            raise UnauthorizedError("Sign in to ask across your library")
    else:
        if viewer.user_id:
            credits_service.charge_wiz_chat_for_video(
                db, viewer.user_id, payload.video_id
            )
        prepare_video(db, payload.video_id)
    conversation = conversations_service.create_conversation(
        db,
        payload.video_id,
        viewer.user_id,
        viewer.guest_session_id,
        payload.scope,
    )
    return ConversationRead.model_validate(conversation)


@router.get(
    "",
    response_model=ConversationList,
    description=(
        "List the user's conversations that have at least one question, latest "
        "first. Filter by scope or video_id to resume a chat."
    ),
)
def list_conversations(
    scope: ConversationScope | None = Query(default=None),
    video_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> ConversationList:
    if video_id is not None:
        try:
            video_id = normalize_youtube_video_id(video_id)
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc
    return conversations_service.list_conversations(
        db, user_id, scope, video_id, page, per_page
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationRead,
    status_code=status.HTTP_200_OK,
    description="Fetch conversation metadata.",
)
def get_conversation(
    conversation=Depends(get_conversation_or_404),
) -> ConversationRead:
    return ConversationRead.model_validate(conversation)


@router.get(
    "/{conversation_id}/messages",
    response_model=list[MessageRead],
    status_code=status.HTTP_200_OK,
    description="List messages for a conversation.",
)
def list_messages(
    conversation=Depends(get_conversation_or_404),
    db: Session = Depends(get_db),
) -> list[MessageRead]:
    messages = conversations_service.list_messages(db, conversation.id)
    return [MessageRead.model_validate(message) for message in messages]


@router.post(
    "/{conversation_id}/messages",
    status_code=status.HTTP_200_OK,
    description="Send a message and stream response via SSE.",
)
@limiter.limit(settings.rate_limit_conversations)
def create_message(
    request: Request,
    response: Response,
    payload: MessageCreate,
    conversation=Depends(get_conversation_or_404),
    db: Session = Depends(get_db),
    viewer: ViewerContext = Depends(get_viewer_context),
):
    if conversation.scope == ConversationScope.LIBRARY:
        system_prompt, references, history, api_key, models = (
            conversations_service.prepare_library_chat(
                db, conversation, payload.message
            )
        )
        return StreamingResponse(
            conversations_service.stream_answer(
                system_prompt=system_prompt,
                references=references,
                history=history,
                conversation_id=conversation.id,
                db=db,
                api_key=api_key,
                models=models,
            ),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    video, transcript, history_serializable, api_key = (
        conversations_service.prepare_chat(db, conversation, viewer, payload.message)
    )
    if transcript is None or video is None or api_key is None:
        response = ChatProcessingResponse(
            status="processing",
            message="Transcript processing",
        )
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED,
            content=response.model_dump(mode="json"),
        )

    return StreamingResponse(
        conversations_service.stream_wiz_response(
            video_title=video.title,
            transcript=transcript,
            history=history_serializable,
            conversation_id=conversation.id,
            db=db,
            api_key=api_key,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
