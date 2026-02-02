from fastapi import Depends
from sqlalchemy.orm import Session

from src.auth.dependencies import get_viewer_context
from src.auth.schemas import ViewerContext
from src.conversations import service as conversations_service
from src.conversations.schemas import ConversationIdPath
from src.database import get_db
from src.exceptions import NotFoundError


def get_conversation_or_404(
    path: ConversationIdPath = Depends(),
    db: Session = Depends(get_db),
    viewer: ViewerContext = Depends(get_viewer_context),
):
    conversation = conversations_service.get_conversation_for_viewer(
        db, path.conversation_id, viewer
    )
    if not conversation:
        raise NotFoundError("Conversation not found")
    return conversation
