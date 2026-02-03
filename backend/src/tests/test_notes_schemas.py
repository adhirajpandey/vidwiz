import pytest
from pydantic import ValidationError

from src.notes.schemas import NoteCreate, NoteUpdate


def test_note_create_validates_timestamp():
    with pytest.raises(ValidationError):
        NoteCreate.model_validate({"timestamp": "123", "text": "note"})

    with pytest.raises(ValidationError):
        NoteCreate.model_validate({"timestamp": "a:b", "text": "note"})

    payload = NoteCreate.model_validate({"timestamp": "01:23", "text": "note"})
    assert payload.timestamp == "01:23"


def test_note_create_normalizes_text():
    payload = NoteCreate.model_validate({"timestamp": "00:01", "text": "  "})
    assert payload.text is None

    payload = NoteCreate.model_validate({"timestamp": "00:01", "text": "  hi  "})
    assert payload.text == "hi"


def test_note_update_forbids_extra_fields():
    with pytest.raises(ValidationError):
        NoteUpdate.model_validate({"text": "ok", "extra": "nope"})
