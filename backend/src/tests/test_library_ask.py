import json
from datetime import date, datetime, timezone

import pytest

from src.ask import retrieval
from src.config import settings
from src.conversations import service as conversations_service
from src.conversations.models import Conversation, ConversationScope
from src.conversations.schemas import MessageCreate
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


TODAY = date(2026, 10, 22)  # A Thursday.


def use_plan(monkeypatch, terms, since=None, until=None, topic=True):
    """Fake the query model's plan; parsing and retrieval stay real."""
    plan = {"terms": terms, "since": since, "until": until, "topic": topic}
    monkeypatch.setattr(
        retrieval, "request_plan", lambda question, history, today: plan
    )
    monkeypatch.setattr(retrieval, "local_today", lambda time_zone: TODAY)


def capture_at(db_session, user, video_id, at, note, created_at):
    moment, _ = moments_service.capture(
        db_session, user.id, CaptureCreate(video=video_id, at=at, note=note, ai=False)
    )
    moment.created_at = created_at
    db_session.flush()
    return moment


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
    # Captured well before the periods the time-range tests ask about.
    capture_at(
        db_session,
        user,
        "fffffffffff",
        62,
        "Phone away helps focus",
        datetime(2026, 9, 1, tzinfo=timezone.utc),
    )


def test_retrieve_keeps_only_relevant_sources(db_session, user, library, monkeypatch):
    use_plan(monkeypatch, ["phone", "distraction", "index"])
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
    use_plan(monkeypatch, ["column"])

    def broken(question, passages):
        raise jev.JevError("down")

    monkeypatch.setattr(jev, "relevance", broken)

    result = retrieval.retrieve(db_session, user.id, "index order", [])

    assert [source.video_id for source in result.sources] == ["ddddddddddd"]
    assert result.relevance_model is None


def test_retrieve_without_candidates_returns_nothing(
    db_session, user, library, monkeypatch
):
    def down(question, history, today):
        raise RuntimeError("model down")

    monkeypatch.setattr(retrieval, "request_plan", down)
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
    use_plan(monkeypatch, ["phone"])
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


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("since", "until", "expected"),
    [
        ("2026-10-19", "2026-10-22", (date(2026, 10, 19), date(2026, 10, 22))),
        # A missing end means up to today; an end after today is cut to today.
        ("2026-10-19", None, (date(2026, 10, 19), TODAY)),
        ("2026-10-19", "2026-10-30", (date(2026, 10, 19), TODAY)),
        (None, None, None),
        (None, "2026-10-20", None),
        ("2026-10-23", "2026-10-25", None),
        ("2026-10-21", "2026-10-20", None),
        ("last week", None, None),
        ("2026-10-19", "soon", None),
    ],
)
def test_parse_time_range_checks_model_dates(since, until, expected):
    time_range = retrieval.parse_time_range(since, until, TODAY, "Asia/Kolkata")
    if expected is None:
        assert time_range is None
    else:
        assert (time_range.since, time_range.until) == expected
        assert time_range.time_zone == "Asia/Kolkata"


def test_time_range_bounds_use_the_users_day():
    time_range = retrieval.TimeRange(
        since=date(2026, 10, 21), until=date(2026, 10, 21), time_zone="Asia/Kolkata"
    )
    start, end = time_range.bounds()
    assert start == utc(2026, 10, 20, 18, 30)
    assert end == utc(2026, 10, 21, 18, 30)


@pytest.mark.parametrize(
    "plan",
    [
        {"since": "2026-10-19"},
        ["phone"],
        {"terms": "phone", "since": None, "until": None, "topic": True},
    ],
)
def test_plan_query_treats_malformed_plans_as_unplanned(monkeypatch, plan):
    monkeypatch.setattr(
        retrieval, "request_plan", lambda question, history, today: plan
    )

    result = retrieval.plan_query("What did I save?", [], "UTC")

    assert result == retrieval.QueryPlan(
        terms=[], time_range=None, has_topic=True, planned=False
    )


def test_time_range_question_reads_newest_moments_in_range(
    db_session, user, library, monkeypatch
):
    use_plan(monkeypatch, [], since="2026-10-19", until="2026-10-22", topic=False)
    monkeypatch.setattr(settings, "ask_time_range_max_sources", 2)

    def no_jev(question, passages):
        raise AssertionError("A period-only question needs no relevance scoring")

    monkeypatch.setattr(jev, "relevance", no_jev)
    old = capture_at(
        db_session, user, "ddddddddddd", 10, "Last month", utc(2026, 9, 30)
    )
    monday = capture_at(
        db_session, user, "ddddddddddd", 40, "Monday", utc(2026, 10, 19, 9)
    )
    tuesday = capture_at(
        db_session, user, "fffffffffff", 5, "Tuesday", utc(2026, 10, 20, 9)
    )
    today = capture_at(
        db_session, user, "ddddddddddd", 90, "Today", utc(2026, 10, 22, 6)
    )

    result = retrieval.retrieve(
        db_session, user.id, "Summarize what I saved this week", [], "Asia/Kolkata"
    )

    # Newest first, capped; transcript passages and older moments are left out.
    assert [source.source_id for source in result.sources] == [
        f"m{today.id}",
        f"m{tuesday.id}",
    ]
    assert f"m{monday.id}" not in {s.source_id for s in result.sources}
    assert f"m{old.id}" not in {s.source_id for s in result.sources}
    assert result.sources[1].context()["captured"] == "2026-10-20"
    assert result.sources[1].video_title == "Deep focus"
    assert result.query_model == settings.ask_query_model
    assert result.relevance_model is None
    assert result.time_range.as_metadata() == {
        "since": "2026-10-19",
        "until": "2026-10-22",
        "time_zone": "Asia/Kolkata",
    }


def test_time_range_with_topic_searches_only_moments_in_range(
    db_session, user, library, monkeypatch
):
    # The fixture's "phone" moment was captured in September, outside last week.
    use_plan(monkeypatch, ["phone"], since="2026-10-12", until="2026-10-18")
    monkeypatch.setattr(
        jev, "relevance", lambda question, passages: [0.9] * len(passages)
    )
    in_range = capture_at(
        db_session, user, "ddddddddddd", 30, "Phone notifications", utc(2026, 10, 14, 9)
    )

    result = retrieval.retrieve(
        db_session, user.id, "What did I save about my phone last week?", [], "UTC"
    )

    assert [source.source_id for source in result.sources] == [f"m{in_range.id}"]
    assert result.relevance_model == settings.jev_model
    assert result.time_range.since == date(2026, 10, 12)


def test_empty_time_range_finds_nothing(db_session, user, library, monkeypatch):
    use_plan(monkeypatch, [], since="2026-10-01", until="2026-10-02", topic=False)

    result = retrieval.retrieve(db_session, user.id, "What did I save?", [], "UTC")

    assert result.sources == []
    assert result.time_range is not None


def test_time_zone_decides_which_day_a_moment_belongs_to(
    db_session, user, library, monkeypatch
):
    # 00:30 on 21 October in India is still 20 October in UTC.
    moment = capture_at(
        db_session, user, "ddddddddddd", 30, "Late night", utc(2026, 10, 20, 19)
    )
    use_plan(monkeypatch, [], since="2026-10-21", until="2026-10-21", topic=False)

    india = retrieval.retrieve(db_session, user.id, "q", [], "Asia/Kolkata")
    utc_day = retrieval.retrieve(db_session, user.id, "q", [], "UTC")

    assert [source.source_id for source in india.sources] == [f"m{moment.id}"]
    assert india.sources[0].captured == date(2026, 10, 21)
    assert utc_day.sources == []


@pytest.mark.parametrize(
    ("time_zone", "expected"),
    [
        ("Asia/Kolkata", "Asia/Kolkata"),
        ("Mars/Olympus", None),
        ("", None),
        (None, None),
    ],
)
def test_message_time_zone_falls_back_when_unknown(time_zone, expected):
    payload = MessageCreate(message="What did I save today?", time_zone=time_zone)
    assert payload.time_zone == expected


@pytest.mark.asyncio
async def test_library_time_range_answer_records_its_period(
    client, db_session, user, library, monkeypatch
):
    use_plan(monkeypatch, [], since="2026-10-19", until="2026-10-22", topic=False)
    seen = {}
    real_retrieve = retrieval.retrieve

    def spy(db, user_id, question, history, time_zone):
        seen["time_zone"] = time_zone
        return real_retrieve(db, user_id, question, history, time_zone)

    monkeypatch.setattr(retrieval, "retrieve", spy)
    moment = capture_at(
        db_session, user, "ddddddddddd", 30, "Index order", utc(2026, 10, 20, 9)
    )
    conversation = Conversation(scope=ConversationScope.LIBRARY, user_id=user.id)
    db_session.add(conversation)
    db_session.flush()
    captured, _ = fake_provider(
        monkeypatch,
        json.dumps(
            {
                "parts": [
                    {
                        "type": "block",
                        "text": "**You saved one moment about index order.**",
                        "references": [
                            {"list_item_index": None, "chunk_ids": [f"m{moment.id}"]}
                        ],
                    }
                ]
            }
        ),
    )

    response = await client.post(
        f"/v2/conversations/{conversation.id}/messages",
        headers=auth_headers(user),
        json={
            "message": "Summarize what I saved this week",
            "time_zone": "Asia/Kolkata",
        },
    )

    assert response.status_code == 200
    assert seen["time_zone"] == "Asia/Kolkata"
    system = captured["messages"][0]["content"]
    assert "from 2026-10-19 to 2026-10-22" in system
    assert '"captured": "2026-10-20"' in system
    saved = conversations_service.list_messages(db_session, conversation.id)
    assert saved[1].metadata_["time_range"] == {
        "since": "2026-10-19",
        "until": "2026-10-22",
        "time_zone": "Asia/Kolkata",
    }
    assert saved[1].metadata_["models"]["relevance_model"] is None
