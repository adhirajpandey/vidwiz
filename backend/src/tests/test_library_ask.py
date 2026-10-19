import json

import pytest

from src.ask import retrieval
from src.config import settings
from src.conversations import service as conversations_service
from src.conversations.models import Conversation, ConversationScope
from src.library.models import LibraryItem
from src.moments import service as moments_service
from src.moments.schemas import CaptureCreate
from src.search.chunks import replace_chunks
from src.shared import jev
from src.tests.test_conversations_parts import fake_provider
from src.tests.test_moments import auth_headers
from src.videos.models import Video

FOCUS = [
    {"text": "Deep work means removing distractions.", "offset": 0, "duration": 5},
    {
        "text": "Put your phone in another room while studying.",
        "offset": 60,
        "duration": 5,
    },
]
DATABASES = [
    {
        "text": "Composite indexes need the right column order.",
        "offset": 10,
        "duration": 5,
    },
]


@pytest.fixture
def library(db_session, user):
    db_session.add_all(
        [
            Video(video_id="fffffffffff", title="Deep focus"),
            Video(video_id="ddddddddddd", title="Databases"),
        ]
    )
    db_session.flush()
    for video_id, transcript in (("fffffffffff", FOCUS), ("ddddddddddd", DATABASES)):
        db_session.add(LibraryItem(user_id=user.id, video_id=video_id))
        replace_chunks(db_session, video_id, transcript)
    moments_service.capture(
        db_session,
        user.id,
        CaptureCreate(
            video="fffffffffff", at=62, note="Phone away helps focus", ai=False
        ),
    )
    db_session.flush()


def test_retrieve_keeps_only_relevant_sources(db_session, user, library, monkeypatch):
    monkeypatch.setattr(
        retrieval,
        "expand_terms",
        lambda question, history: ["phone", "distraction", "index"],
    )
    seen = {}

    def fake_relevance(question, passages):
        seen["passages"] = passages
        return [0.1 if "index" in passage.lower() else 0.9 for passage in passages]

    monkeypatch.setattr(jev, "relevance", fake_relevance)

    result = retrieval.retrieve(db_session, user.id, "How do I stay focused?", [])
    sources = result.sources
    assert result.query_model == settings.ask_query_model
    assert result.relevance_model == settings.jev_model

    kinds = {source.kind for source in sources}
    assert kinds == {"moment", "transcript"}
    assert all(source.video_id == "fffffffffff" for source in sources)
    # The database passage was a candidate, but Jev filtered it out.
    assert any("Composite" in passage for passage in seen["passages"])
    moment = next(source for source in sources if source.kind == "moment")
    assert moment.source_id.startswith("m")
    assert "User note: Phone away helps focus" in moment.text


def test_retrieve_falls_back_to_full_text_when_jev_fails(
    db_session, user, library, monkeypatch
):
    monkeypatch.setattr(retrieval, "expand_terms", lambda question, history: ["column"])

    def broken(question, passages):
        raise jev.JevError("down")

    monkeypatch.setattr(jev, "relevance", broken)

    result = retrieval.retrieve(db_session, user.id, "index order", [])

    assert [source.video_id for source in result.sources] == ["ddddddddddd"]
    assert result.relevance_model is None


def test_retrieve_without_candidates_returns_nothing(
    db_session, user, library, monkeypatch
):
    monkeypatch.setattr(retrieval, "expand_terms", lambda question, history: [])
    monkeypatch.setattr(settings, "jev_enabled", False)

    result = retrieval.retrieve(db_session, user.id, "quantum zebra", [])
    assert result.sources == []
    assert result.query_model is None


def test_jev_relevance_batches_and_validates(monkeypatch):
    calls = []

    def fake_decide(state, questions):
        calls.append(len(state["passages"]))
        return {key: {"type": "noul", "noul": 0.5} for key in questions}

    monkeypatch.setattr(jev, "decide", fake_decide)
    assert jev.relevance("q", ["text"] * 30) == [0.5] * 30
    assert sorted(calls) == [6, 12, 12]

    monkeypatch.setattr(jev, "decide", lambda state, questions: {})
    with pytest.raises(jev.JevError):
        jev.relevance("q", ["text"])


@pytest.mark.asyncio
async def test_library_message_streams_cited_answer(
    client, db_session, user, library, monkeypatch
):
    monkeypatch.setattr(retrieval, "expand_terms", lambda question, history: ["phone"])
    monkeypatch.setattr(
        jev, "relevance", lambda question, passages: [0.9] * len(passages)
    )
    conversation = Conversation(scope=ConversationScope.LIBRARY, user_id=user.id)
    db_session.add(conversation)
    db_session.flush()
    source_id = (
        retrieval.retrieve(db_session, user.id, "phone", []).sources[0].source_id
    )
    captured, _ = fake_provider(
        monkeypatch,
        json.dumps(
            {
                "parts": [
                    {
                        "type": "block",
                        "text": "**Keep your phone away.**",
                        "references": [
                            {"list_item_index": None, "chunk_ids": [source_id]}
                        ],
                    }
                ]
            }
        ),
    )

    response = await client.post(
        f"/v2/conversations/{conversation.id}/messages",
        headers=auth_headers(user),
        json={"message": "How do I stay focused with my phone around?"},
    )

    assert response.status_code == 200
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    block = events[0]
    passage = block["citations"][0]["passages"][0]
    assert passage["video_id"] == "fffffffffff"
    assert events[-1]["type"] == "done"
    assert "Sources" in captured["messages"][0]["content"]
    assert "Deep focus" in captured["messages"][0]["content"]
    saved = conversations_service.list_messages(db_session, conversation.id)
    assert [message.role for message in saved] == ["user", "assistant"]
    assert saved[1].metadata_["models"] == {
        "model": settings.wiz_model,
        "query_model": settings.ask_query_model,
        "relevance_model": settings.jev_model,
    }
