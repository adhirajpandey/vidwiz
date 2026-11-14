import copy
import json
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from src.ask import loop
from src.ask.prompts import FINAL_ROUND_MESSAGE, LOOK_UP_MESSAGE
from src.config import settings
from src.conversations import service as conversations_service
from src.conversations.models import Conversation, ConversationScope
from src.conversations.schemas import MessageCreate
from src.conversations.parts import (
    BlockPart,
    DigestPart,
    ErrorEvent,
    StatsPart,
    StatusEvent,
    history_parts,
    stored_parts,
    text_projection,
)
from src.library.models import LibraryItem
from src.moments import service as moments_service
from src.moments.schemas import CaptureCreate
from src.search.chunks import replace_chunks
from src.search.models import TranscriptChunk
from src.shared import jev
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
QUESTION = "How do I stay focused with my phone around?"


def utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def capture_at(db_session, user, video_id, at, note, created_at):
    moment, _ = moments_service.capture(
        db_session,
        user.id,
        CaptureCreate(video=video_id, at=at, note=note, ai=False),
        lambda *_: None,
    )
    moment.created_at = created_at
    db_session.flush()
    return moment


@pytest.fixture
def library(db_session, user):
    db_session.add_all(
        [
            Video(
                video_id="fffffffffff",
                title="Deep focus",
                video_metadata={"uploader": "Focus Lab"},
            ),
            Video(video_id="ddddddddddd", title="Databases"),
        ]
    )
    db_session.flush()
    for video_id, transcript in (("fffffffffff", FOCUS), ("ddddddddddd", DATABASES)):
        db_session.add(LibraryItem(user_id=user.id, video_id=video_id))
        replace_chunks(db_session, video_id, transcript)
    capture_at(
        db_session, user, "fffffffffff", 62, "Phone away helps focus", utc(2026, 9, 1)
    )


def phone_chunk(db_session) -> str:
    chunk = db_session.execute(
        select(TranscriptChunk).where(
            TranscriptChunk.video_id == "fffffffffff", TranscriptChunk.idx == 1
        )
    ).scalar_one()
    return f"c{chunk.id}"


# ---- a scripted chat model ----


def chunk(content=None, tool_calls=None, finish=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content, tool_calls=tool_calls),
                finish_reason=finish,
            )
        ]
    )


def tool_round(*calls):
    """Tool calls as streamed deltas, each call's arguments split in two."""
    chunks = []
    for index, (name, arguments) in enumerate(calls):
        text = json.dumps(arguments)
        half = len(text) // 2
        chunks.append(
            chunk(
                tool_calls=[
                    SimpleNamespace(
                        index=index,
                        id=f"call_{name}_{index}",
                        function=SimpleNamespace(name=name, arguments=text[:half]),
                    )
                ]
            )
        )
        chunks.append(
            chunk(
                tool_calls=[
                    SimpleNamespace(
                        index=index,
                        id=None,
                        function=SimpleNamespace(name=None, arguments=text[half:]),
                    )
                ]
            )
        )
    chunks.append(chunk(finish="tool_calls"))
    return chunks


def done_round(text="I have what I need."):
    """A tool round that ends with text and no tool calls."""
    return [chunk(content=text), chunk(finish="stop")]


def answer_round(*blocks, finish="stop", raw=None):
    payload = raw if raw is not None else json.dumps({"parts": list(blocks)})
    chunks = [chunk(content=payload[i : i + 7]) for i in range(0, len(payload), 7)]
    chunks.append(chunk(finish=finish))
    return chunks


def block(text, *chunk_ids, index=None):
    return {
        "type": "block",
        "text": text,
        "references": (
            [{"list_item_index": index, "chunk_ids": list(chunk_ids)}]
            if chunk_ids
            else []
        ),
    }


class FakeModel:
    def __init__(self, monkeypatch, rounds):
        self.rounds = list(rounds)
        self.requests = []
        self.closed = 0
        monkeypatch.setattr(
            loop,
            "OpenAI",
            lambda **kw: SimpleNamespace(
                chat=SimpleNamespace(completions=SimpleNamespace(create=self.create))
            ),
        )

    def create(self, **kwargs):
        self.requests.append(copy.deepcopy(kwargs))
        current = self.rounds.pop(0)
        if isinstance(current, Exception):
            raise current
        model = self

        class Stream:
            def __iter__(self):
                yield from current

            def close(self):
                model.closed += 1

        return Stream()


def run(db_session, user, question=QUESTION, history=None, **kwargs):
    items = list(
        loop.run_ask(
            db_session, user.id, question, history or [], "UTC", "key", **kwargs
        )
    )
    result = items[-1]
    assert isinstance(result, loop.LoopResult)
    return items[:-1], result


def tool_messages(request):
    return [
        json.loads(m["content"]) for m in request["messages"] if m["role"] == "tool"
    ]


@pytest.fixture
def strong(monkeypatch):
    calls = []

    def relevance(question, passages, timeout):
        calls.append((question, passages, timeout))
        return [0.9] * len(passages)

    monkeypatch.setattr(jev, "relevance", relevance)
    return calls


# ---- the loop ----


def test_answers_after_tool_calls_with_citations(
    db_session, user, library, strong, monkeypatch
):
    source_id = phone_chunk(db_session)
    model = FakeModel(
        monkeypatch,
        [
            tool_round(("search", {"query": "phone focus"})),
            done_round(),
            answer_round(
                block("**Keep your phone away.**", source_id),
                block("Invented.", "c999999"),
            ),
        ],
    )

    events, result = run(db_session, user)

    assert result.failure is None
    first, second, answer = model.requests
    assert first["model"] == settings.ask_model == "z-ai/glm-5.3-flash"
    assert first["temperature"] == 0
    assert first["max_tokens"] == 2500
    assert first["stream"] is True
    assert first["tools"] == loop.TOOL_SPECS
    # The first round must call a tool; later rounds may answer.
    assert first["tool_choice"] == "required"
    assert "tool_choice" not in second
    # Tool rounds carry no schema; the answer round has no tools.
    assert "response_format" not in first
    assert "tools" not in answer
    assert answer["response_format"]["json_schema"]["strict"] is True
    assert answer["messages"][-1]["content"] == FINAL_ROUND_MESSAGE
    assert first["extra_body"] == {
        "reasoning": {"effort": "low"},
        "provider": {"require_parameters": True},
    }
    assert first["messages"][0]["role"] == "system"
    assert "Today is" in first["messages"][0]["content"]
    assert first["messages"][-1] == {"role": "user", "content": QUESTION}
    # The split argument deltas were joined into one call.
    call = second["messages"][-2]["tool_calls"][0]
    assert call["function"] == {
        "name": "search",
        "arguments": json.dumps({"query": "phone focus"}),
    }
    assert second["messages"][-1]["tool_call_id"] == call["id"]
    assert any(r["id"] == source_id for r in tool_messages(second)[0]["results"])

    blocks = [e for e in events if isinstance(e, BlockPart)]
    assert blocks == result.blocks
    passage = blocks[0].citations[0].passages[0]
    assert passage.chunk_ids == [source_id]
    assert passage.video_id == "fffffffffff"
    # An id the tools never returned is dropped.
    assert blocks[1].citations == []
    assert [s.source_id for s in result.cited] == [source_id]
    assert result.stats.rounds == 3
    assert result.stats.searches == 1
    assert result.stats.limit_reached is False
    assert model.closed == 3


def test_status_events_name_each_tool(db_session, user, library, strong, monkeypatch):
    FakeModel(
        monkeypatch,
        [
            tool_round(
                ("find_videos", {}),
                ("search", {"query": "phone"}),
                ("moments_in", {"since": "2026-09-01", "until": "2026-09-30"}),
                ("library_stats", {}),
                ("not_a_tool", {}),
            ),
            done_round(),
            answer_round(block("Done.")),
        ],
    )

    events, _ = run(db_session, user)

    assert [e.text for e in events if isinstance(e, StatusEvent)] == [
        "Looking through your videos",
        "Searching your library",
        "Collecting your moments",
        "Counting your videos",
    ]


def test_tool_error_result_reaches_the_model(db_session, user, library, monkeypatch):
    model = FakeModel(
        monkeypatch,
        [
            tool_round(("fetch", {"source_id": "c1"})),
            done_round(),
            answer_round(block("Not in your library.")),
        ],
    )

    _, result = run(db_session, user)

    assert result.failure is None
    assert tool_messages(model.requests[1]) == [
        {"error": "Use a source ID already returned by a tool."}
    ]


def test_tool_call_limit(db_session, user, library, monkeypatch):
    model = FakeModel(
        monkeypatch,
        [
            tool_round(*[("library_stats", {})] * 4),
            tool_round(*[("library_stats", {})] * 4),
            answer_round(block("Done.")),
        ],
    )

    _, result = run(db_session, user)

    outputs = tool_messages(model.requests[2])
    assert len(outputs) == 8
    assert all("video_count" in output for output in outputs[:6])
    assert outputs[6:] == [{"error": loop.TOOL_LIMIT_ERROR}] * 2
    assert len(result.stats.tools) == 6
    assert result.stats.limit_reached
    # Six calls ran, so the next round is the forced final one.
    final = model.requests[2]
    assert "tools" not in final
    assert final["messages"][-1] == {"role": "user", "content": FINAL_ROUND_MESSAGE}


def test_search_limit(db_session, user, library, strong, monkeypatch):
    model = FakeModel(
        monkeypatch,
        [
            tool_round(*[("search", {"query": f"phone {i}"}) for i in range(5)]),
            done_round(),
            answer_round(block("Done.")),
        ],
    )

    _, result = run(db_session, user)

    outputs = tool_messages(model.requests[1])
    assert all("results" in output for output in outputs[:4])
    assert outputs[4] == {"error": loop.SEARCH_LIMIT_ERROR}
    assert result.stats.searches == 4
    assert len(strong) == 4
    assert result.stats.limit_reached


def test_round_five_is_forced_to_answer(db_session, user, library, monkeypatch):
    model = FakeModel(
        monkeypatch,
        [*[tool_round(("library_stats", {}))] * 4, answer_round(block("Done."))],
    )

    _, result = run(db_session, user)

    assert result.failure is None
    assert result.stats.rounds == 5
    assert all("tools" in request for request in model.requests[:4])
    final = model.requests[4]
    assert "tools" not in final
    assert final["response_format"]["type"] == "json_schema"
    assert final["messages"][-1]["content"] == FINAL_ROUND_MESSAGE
    # The forced message is not kept in the conversation itself.
    assert FINAL_ROUND_MESSAGE not in [m.get("content") for m in final["messages"][:-1]]


def test_tool_calls_in_the_forced_round_are_not_run(
    db_session, user, library, monkeypatch
):
    FakeModel(
        monkeypatch,
        [*[tool_round(("library_stats", {}))] * 5],
    )

    events, result = run(db_session, user)

    assert len(result.stats.tools) == 4
    assert result.failure == "empty_response"
    assert isinstance(events[-1], ErrorEvent)


def test_tool_rounds_never_show_their_text(db_session, user, library, monkeypatch):
    long_draft = "A draft answer that is never shown. " * 30
    model = FakeModel(
        monkeypatch,
        [
            [chunk(content="Let me check."), *tool_round(("library_stats", {}))],
            [chunk(content=long_draft[i : i + 20]) for i in range(0, 1000, 20)],
            answer_round(block("**You have two videos.**")),
        ],
    )

    events, result = run(db_session, user)

    assert result.failure is None
    assert [e.text for e in events if isinstance(e, BlockPart)] == [
        "**You have two videos.**"
    ]
    tool_request, draft_request, answer_request = model.requests
    for request in (tool_request, draft_request):
        assert request["tools"] == loop.TOOL_SPECS
        assert "response_format" not in request
    assert "tools" not in answer_request
    assert answer_request["response_format"]["json_schema"]["strict"] is True
    assert answer_request["messages"][-1]["content"] == FINAL_ROUND_MESSAGE
    # The long draft was cut off instead of read to the end.
    assert model.closed == 3
    assert result.stats.limit_reached is False


def test_text_before_any_lookup_is_sent_back(db_session, user, library, monkeypatch):
    model = FakeModel(
        monkeypatch,
        [
            done_round("Let me search your library first."),
            tool_round(("library_stats", {})),
            done_round(),
            answer_round(block("**You have two videos.**")),
        ],
    )

    _, result = run(db_session, user)

    assert result.failure is None
    nudged = model.requests[1]
    assert nudged["messages"][-1] == {"role": "user", "content": LOOK_UP_MESSAGE}
    assert nudged["tool_choice"] == "required"
    assert "tool_choice" not in model.requests[2]
    assert result.stats.rounds == 4


def test_find_videos_alone_is_not_enough_to_answer(
    db_session, user, library, monkeypatch
):
    model = FakeModel(
        monkeypatch,
        [
            tool_round(("find_videos", {})),
            done_round("Found it, let me look inside."),
            done_round("Found it, let me look inside."),
            tool_round(("search", {"query": "phone"})),
            answer_round(block("**Deep focus covers it.**")),
        ],
    )

    _, result = run(db_session, user)

    assert result.failure is None
    # Lookups stay required until something was read; one nudge is enough.
    assert all(r["tool_choice"] == "required" for r in model.requests[:4])
    contents = [m.get("content") for m in model.requests[3]["messages"]]
    assert contents.count(LOOK_UP_MESSAGE) == 1
    # The search ran in round four, so round five is the forced answer.
    assert result.stats.rounds == 5
    assert [b.text for b in result.blocks] == ["**Deep focus covers it.**"]


@pytest.mark.parametrize(
    ("final_round", "failure"),
    [
        (answer_round(raw=""), "empty_response"),
        (answer_round(raw='{"parts": [{"type": "block"'), "invalid_output"),
        (answer_round(block("Cut off."), finish="length"), "invalid_output"),
        (RuntimeError("provider down"), "model_error"),
    ],
)
def test_failures_end_with_an_error(
    db_session, user, library, final_round, failure, monkeypatch
):
    FakeModel(
        monkeypatch, [tool_round(("library_stats", {})), done_round(), final_round]
    )

    events, result = run(db_session, user)

    assert result.failure == failure
    assert isinstance(events[-1], ErrorEvent)
    assert not any(isinstance(e, StatsPart) for e in events)


# ---- relevance ----


def test_marks_use_the_question_not_the_query(db_session, user, library, monkeypatch):
    seen = []

    def relevance(question, passages, timeout):
        seen.append((question, timeout))
        return [0.9 if "phone" in p.lower() else 0.1 for p in passages]

    monkeypatch.setattr(jev, "relevance", relevance)
    model = FakeModel(
        monkeypatch,
        [
            tool_round(("search", {"query": "phone"})),
            done_round(),
            answer_round(block("Done.")),
        ],
    )

    _, result = run(db_session, user)

    assert seen == [(QUESTION, 3)]
    output = tool_messages(model.requests[1])[0]
    marks = {r["text"]: r["match"] for r in output["results"]}
    assert "strong" in marks.values()
    assert all(
        mark == ("strong" if "phone" in text.lower() else "weak")
        for text, mark in marks.items()
    )
    assert "note" not in output
    assert result.models == {
        "model": settings.ask_model,
        "relevance_model": settings.jev_model,
    }


def test_no_strong_match_adds_a_note(db_session, user, library, monkeypatch):
    monkeypatch.setattr(jev, "relevance", lambda q, p, timeout: [0.2] * len(p))
    model = FakeModel(
        monkeypatch,
        [
            tool_round(("search", {"query": "phone"})),
            done_round(),
            answer_round(block("Done.")),
        ],
    )

    run(db_session, user)

    output = tool_messages(model.requests[1])[0]
    assert output["results"]
    assert {r["match"] for r in output["results"]} == {"weak"}
    assert output["note"] == loop.NO_STRONG_MATCH_NOTE


def test_jev_failure_sends_results_unmarked(db_session, user, library, monkeypatch):
    def broken(question, passages, timeout):
        raise jev.JevError("down")

    monkeypatch.setattr(jev, "relevance", broken)
    model = FakeModel(
        monkeypatch,
        [
            tool_round(("search", {"query": "phone"})),
            done_round(),
            answer_round(block("Done.")),
        ],
    )

    _, result = run(db_session, user)

    output = tool_messages(model.requests[1])[0]
    assert output["results"]
    assert all("match" not in r for r in output["results"])
    assert "note" not in output
    assert result.failure is None
    assert result.models["relevance_model"] is None


def test_slow_jev_times_out(db_session, user, library, monkeypatch):
    def slow(state, questions, timeout):
        time.sleep(1)
        return {key: {"noul": 0.9} for key in questions}

    monkeypatch.setattr(jev, "decide", slow)
    monkeypatch.setattr(loop, "RELEVANCE_TIMEOUT_SECONDS", 0.05)
    model = FakeModel(
        monkeypatch,
        [
            tool_round(("search", {"query": "phone"})),
            done_round(),
            answer_round(block("Done.")),
        ],
    )

    started = time.perf_counter()
    _, result = run(db_session, user)

    assert time.perf_counter() - started < 0.9
    output = tool_messages(model.requests[1])[0]
    assert all("match" not in r for r in output["results"])
    assert result.failure is None


def test_relevance_can_be_turned_off(db_session, user, library, monkeypatch):
    def never(*args, **kwargs):
        raise AssertionError("Jev must not be called")

    monkeypatch.setattr(jev, "relevance", never)
    model = FakeModel(
        monkeypatch,
        [
            tool_round(("search", {"query": "phone"})),
            done_round(),
            answer_round(block("Done.")),
        ],
    )

    answer = loop.ask(db_session, user.id, QUESTION, relevance=False, api_key="k")

    assert answer.result.failure is None
    assert answer.text == "Done."
    output = tool_messages(model.requests[1])[0]
    assert all("match" not in r for r in output["results"])


def test_jev_relevance_batches_and_validates(monkeypatch):
    calls = []

    def fake_decide(state, questions, timeout):
        calls.append(len(state["passages"]))
        return {key: {"type": "noul", "noul": 0.5} for key in questions}

    monkeypatch.setattr(jev, "decide", fake_decide)
    assert jev.relevance("q", ["text"] * 30) == [0.5] * 30
    assert sorted(calls) == [6, 12, 12]

    monkeypatch.setattr(jev, "decide", lambda state, questions, timeout: {})
    with pytest.raises(jev.JevError):
        jev.relevance("q", ["text"])


# ---- typed parts ----


def test_digest_and_stats_follow_the_blocks(db_session, user, library, monkeypatch):
    later = capture_at(
        db_session, user, "ddddddddddd", 30, "Index order", utc(2026, 9, 3)
    )
    FakeModel(
        monkeypatch,
        [
            tool_round(
                ("moments_in", {"since": "2026-09-01", "until": "2026-09-30"}),
                ("library_stats", {"group_by": "channel"}),
            ),
            done_round(),
            answer_round(block("**You saved two moments.**")),
        ],
    )

    events, result = run(db_session, user)

    kinds = [type(e).__name__ for e in events if not isinstance(e, StatusEvent)]
    assert kinds == ["BlockPart", "DigestPart", "StatsPart"]
    digest, stats = result.typed_parts
    assert digest.since == "2026-09-01" and digest.until == "2026-09-30"
    assert (digest.total_moments, digest.video_count) == (2, 2)
    assert [v.title for v in digest.videos] == ["Deep focus", "Databases"]
    assert digest.videos[1].moments[0].id == f"m{later.id}"
    assert digest.videos[1].moments[0].at_seconds == 30
    assert stats.group_by == "channel"
    assert stats.video_count is None
    assert {(g.name, g.videos) for g in stats.groups} == {
        ("Focus Lab", 1),
        ("Unknown channel", 1),
    }


def test_digest_carries_more_than_the_model_sees(
    db_session, user, library, monkeypatch
):
    for second in range(10):
        capture_at(
            db_session,
            user,
            "ddddddddddd",
            second * 30,
            f"Note {second}",
            utc(2026, 10, 1, 9, second),
        )
    model = FakeModel(
        monkeypatch,
        [
            tool_round(("moments_in", {"since": "2026-10-01", "until": "2026-10-01"})),
            done_round(),
            answer_round(block("Ten moments.")),
        ],
    )

    _, result = run(db_session, user)

    seen = tool_messages(model.requests[1])[0]
    assert len(seen["videos"][0]["moments"]) == 6
    digest = result.typed_parts[0]
    assert digest.videos[0].moment_count == 10
    assert len(digest.videos[0].moments) == 10


def test_last_successful_stats_call_wins(db_session, user, library, monkeypatch):
    FakeModel(
        monkeypatch,
        [
            tool_round(
                ("library_stats", {}),
                ("library_stats", {"channel": "zzzz nobody"}),
            ),
            done_round(),
            answer_round(raw='{"parts": []}'),
        ],
    )

    _, result = run(db_session, user)

    # Only typed parts is still a valid answer.
    assert result.failure is None
    assert result.blocks == []
    (stats,) = result.typed_parts
    assert stats.video_count == 2 and stats.group_by is None


def test_typed_part_text_forms():
    digest = DigestPart(
        type="digest",
        since="2026-11-03",
        until="2026-11-09",
        total_moments=79,
        video_count=17,
        videos=[],
    )
    count = StatsPart(type="stats", video_count=649, group_by=None, groups=None)
    groups = StatsPart(
        type="stats",
        video_count=None,
        group_by="channel",
        groups=[{"name": "A", "videos": 12}, {"name": "B", "videos": 5}],
    )
    assert text_projection([digest]) == (
        "Digest: 79 moments in 17 videos, 2026-11-03 to 2026-11-09"
    )
    assert text_projection([count]) == "Stats: 649 videos"
    assert text_projection([groups]) == "Stats by channel: A (12), B (5)"
    assert history_parts([digest, count], {}) == [
        {
            "type": "block",
            "text": "Digest: 79 moments in 17 videos, 2026-11-03 to 2026-11-09",
            "references": [],
        },
        {"type": "block", "text": "Stats: 649 videos", "references": []},
    ]


def test_history_replays_earlier_answers_with_typed_parts(
    db_session, user, library, monkeypatch
):
    model = FakeModel(
        monkeypatch,
        [
            tool_round(("library_stats", {})),
            done_round(),
            answer_round(block("Again.")),
        ],
    )
    history = [
        {"role": "user", "content": "How many videos?", "metadata": None},
        {
            "role": "assistant",
            "content": "Two.",
            "metadata": {
                "parts_version": 2,
                "parts": [
                    {
                        "type": "block",
                        "text": "Two.",
                        "citations": [
                            {
                                "list_item_index": None,
                                "passages": [
                                    {
                                        "chunk_ids": ["c1"],
                                        "start_seconds": 0,
                                        "end_seconds": 5,
                                        "video_id": "fffffffffff",
                                    }
                                ],
                            }
                        ],
                    },
                    {
                        "type": "stats",
                        "video_count": 2,
                        "group_by": None,
                        "groups": None,
                    },
                ],
            },
        },
    ]

    run(db_session, user, "And now?", history)

    messages = model.requests[0]["messages"]
    assert messages[1] == {"role": "user", "content": "How many videos?"}
    assert json.loads(messages[2]["content"]) == {
        "parts": [
            {"type": "block", "text": "Two.", "references": []},
            {"type": "block", "text": "Stats: 2 videos", "references": []},
        ]
    }
    assert messages[3] == {"role": "user", "content": "And now?"}


# ---- the route ----


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


def library_conversation(db_session, user):
    conversation = Conversation(scope=ConversationScope.LIBRARY, user_id=user.id)
    db_session.add(conversation)
    db_session.flush()
    return conversation


def sse(text):
    return [
        json.loads(line.removeprefix("data: "))
        for line in text.splitlines()
        if line.startswith("data: ")
    ]


@pytest.mark.asyncio
async def test_route_streams_and_saves_the_answer(
    client, db_session, user, library, strong, monkeypatch
):
    conversation = library_conversation(db_session, user)
    source_id = phone_chunk(db_session)
    model = FakeModel(
        monkeypatch,
        [
            tool_round(
                ("search", {"query": "phone"}),
                ("moments_in", {"since": "2026-09-01", "until": "2026-09-30"}),
            ),
            done_round(),
            answer_round(block("**Keep your phone away.**", source_id)),
        ],
    )

    response = await client.post(
        f"/v2/conversations/{conversation.id}/messages",
        headers=auth_headers(user),
        json={"message": QUESTION, "time_zone": "Asia/Kolkata"},
    )

    assert response.status_code == 200
    events = sse(response.text)
    assert [e["type"] for e in events] == [
        "status",
        "status",
        "block",
        "digest",
        "done",
    ]
    assert events[2]["citations"][0]["passages"][0]["video_id"] == "fffffffffff"
    assert "Asia/Kolkata" not in model.requests[0]["messages"][0]["content"]
    saved = conversations_service.list_messages(db_session, conversation.id)
    assert [m.role for m in saved] == ["user", "assistant"]
    assert saved[1].id == events[-1]["message_id"]
    metadata = saved[1].metadata_
    assert [p["type"] for p in metadata["parts"]] == ["block", "digest"]
    assert metadata["models"] == {
        "model": settings.ask_model,
        "relevance_model": settings.jev_model,
    }
    assert saved[1].content == (
        "**Keep your phone away.**\n\n"
        "Digest: 1 moment in 1 video, 2026-09-01 to 2026-09-30"
    )
    # Stored typed parts load back through the messages endpoint.
    listed = await client.get(
        f"/v2/conversations/{conversation.id}/messages", headers=auth_headers(user)
    )
    parts = listed.json()[1]["parts"]
    assert parts[1]["type"] == "digest"
    assert parts[1]["videos"][0]["moments"][0]["text"] == "Phone away helps focus"
    loaded = stored_parts(saved[1].content, metadata)
    assert isinstance(loaded[1], DigestPart)


@pytest.mark.asyncio
async def test_route_passes_the_time_zone_and_prior_history(
    client, db_session, user, library, monkeypatch
):
    conversation = library_conversation(db_session, user)
    seen = {}
    real = loop.run_ask

    def spy(db, user_id, question, history, time_zone, api_key, relevance=True):
        seen.update(question=question, history=history, time_zone=time_zone)
        return real(db, user_id, question, history, time_zone, api_key, relevance)

    monkeypatch.setattr(loop, "run_ask", spy)
    FakeModel(
        monkeypatch,
        [
            tool_round(("library_stats", {})),
            done_round(),
            answer_round(block("One.")),
            tool_round(("library_stats", {})),
            done_round(),
            answer_round(block("Two.")),
        ],
    )

    for message in ("First?", "Second?"):
        response = await client.post(
            f"/v2/conversations/{conversation.id}/messages",
            headers=auth_headers(user),
            json={"message": message, "time_zone": "Mars/Olympus"},
        )
        assert response.status_code == 200

    assert seen["time_zone"] == loop.DEFAULT_TIME_ZONE
    assert seen["question"] == "Second?"
    assert [(m["role"], m["content"]) for m in seen["history"]] == [
        ("user", "First?"),
        ("assistant", "One.\n\nStats: 2 videos"),
    ]


@pytest.mark.asyncio
async def test_route_quota_counts_one_question(
    client, db_session, user, library, monkeypatch
):
    conversation = library_conversation(db_session, user)
    monkeypatch.setattr(settings, "wiz_user_daily_quota", 1)
    model = FakeModel(
        monkeypatch,
        [
            tool_round(("library_stats", {})),
            done_round(),
            answer_round(block("Two videos.")),
        ],
    )

    first = await client.post(
        f"/v2/conversations/{conversation.id}/messages",
        headers=auth_headers(user),
        json={"message": "How many?"},
    )
    second = await client.post(
        f"/v2/conversations/{conversation.id}/messages",
        headers=auth_headers(user),
        json={"message": "And now?"},
    )

    assert first.status_code == 200
    assert sse(first.text)[-1]["type"] == "done"
    assert second.status_code == 429
    assert len(model.requests) == 3


@pytest.mark.asyncio
async def test_route_chat_error_saves_no_answer(
    client, db_session, user, library, monkeypatch
):
    conversation = library_conversation(db_session, user)
    FakeModel(monkeypatch, [RuntimeError("provider down")])

    response = await client.post(
        f"/v2/conversations/{conversation.id}/messages",
        headers=auth_headers(user),
        json={"message": QUESTION},
    )

    assert sse(response.text) == [{"type": "error", "message": "Processing error"}]
    saved = conversations_service.list_messages(db_session, conversation.id)
    assert [m.role for m in saved] == ["user"]


def test_disconnect_stops_the_loop_and_saves_nothing(
    db_session, user, library, monkeypatch
):
    conversation = library_conversation(db_session, user)
    outcomes = []
    monkeypatch.setattr(
        conversations_service,
        "record_workflow_event",
        lambda workflow, name, reason: outcomes.append((name, reason)),
    )
    model = FakeModel(
        monkeypatch,
        [
            tool_round(("library_stats", {}), ("find_videos", {})),
            done_round(),
            answer_round(block("Never sent.")),
        ],
    )
    stream = conversations_service.stream_library_answer(
        db=db_session,
        conversation=conversation,
        question="How many?",
        history=[],
        time_zone=None,
        api_key="key",
    )

    assert json.loads(next(stream).removeprefix("data: "))["type"] == "status"
    stream.close()

    assert len(model.requests) == 1
    assert model.closed == 1
    assert conversations_service.list_messages(db_session, conversation.id) == []
    assert outcomes == [("wiz_interrupted", "interrupted")]


def test_video_chat_still_uses_the_wiz_model(db_session, monkeypatch):
    from src.tests.test_conversations_parts import fake_provider, run_stream

    captured, _ = fake_provider(
        monkeypatch,
        json.dumps({"parts": [block("Answer.")]}),
    )

    events, saved = run_stream(db_session)

    assert captured["model"] == settings.wiz_model
    assert "tools" not in captured
    assert [e["type"] for e in events] == ["block", "done"]
    assert saved[-1].metadata_["models"] == {"model": settings.wiz_model}
