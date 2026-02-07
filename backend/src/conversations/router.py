from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from src.auth.dependencies import get_viewer_context
from src.auth.schemas import ViewerContext
from src.config import settings
from src.conversations import service as conversations_service
from src.conversations.dependencies import get_conversation_or_404
from src.conversations.schemas import (
    ChatProcessingResponse,
    ConversationCreate,
    ConversationRead,
    MessageCreate,
    MessageRead,
)
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
    request: Request,
    response: Response,
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    viewer: ViewerContext = Depends(get_viewer_context),
) -> ConversationRead:
    _video, _ = conversations_service.get_or_create_video(db, payload.video_id)
    conversation = conversations_service.create_conversation(
        db,
        payload.video_id,
        viewer.user_id,
        viewer.guest_session_id,
    )
    return ConversationRead.model_validate(conversation)


@router.get(
    "/{conversation_id}",
    response_model=ConversationRead,
    status_code=status.HTTP_200_OK,
    description="Fetch conversation metadata.",
)
def get_conversation(
    request: Request,
    response: Response,
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
    request: Request,
    response: Response,
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
