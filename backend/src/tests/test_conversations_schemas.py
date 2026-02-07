import pytest
from pydantic import ValidationError

from src.conversations.schemas import ConversationCreate, MessageCreate


def test_conversation_create_validates_video_id():
    payload = ConversationCreate.model_validate({"video_id": "abc123DEF45"})
    assert payload.video_id == "abc123DEF45"

    with pytest.raises(ValidationError):
        ConversationCreate.model_validate({"video_id": "bad"})


def test_conversation_create_forbids_extra_fields():
    with pytest.raises(ValidationError):
        ConversationCreate.model_validate({"video_id": "abc123DEF45", "extra": "nope"})


def test_message_create_trims_and_validates():
    payload = MessageCreate.model_validate({"message": "  hello  "})
    assert payload.message == "hello"

    with pytest.raises(ValidationError):
        MessageCreate.model_validate({"message": "   "})


def test_message_create_forbids_extra_fields():
    with pytest.raises(ValidationError):
        MessageCreate.model_validate({"message": "hi", "extra": "nope"})
