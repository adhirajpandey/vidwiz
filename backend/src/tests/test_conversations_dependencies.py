import pytest

from src.auth.schemas import ViewerContext
from src.conversations import dependencies as conversations_dependencies
from src.conversations import service as conversations_service
from src.exceptions import NotFoundError


def test_get_conversation_or_404_scopes_by_guest(db_session):
    conversation = conversations_service.create_conversation(
        db_session, "abc123DEF45", None, "guest-1"
    )

    path = conversations_dependencies.ConversationIdPath.model_validate(
        {"conversation_id": conversation.id}
    )
    viewer = ViewerContext(guest_session_id="guest-1")
    found = conversations_dependencies.get_conversation_or_404(
        path=path, db=db_session, viewer=viewer
    )
    assert found.id == conversation.id

    other_viewer = ViewerContext(guest_session_id="guest-2")
    with pytest.raises(NotFoundError):
        conversations_dependencies.get_conversation_or_404(
            path=path, db=db_session, viewer=other_viewer
        )
