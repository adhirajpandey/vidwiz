import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.config import settings
from src.conversations import service
from src.conversations.models import Conversation
from src.conversations.parts import (
    CitationPart,
    PartsDecoder,
    TextPart,
    transcript_context,
)
from src.conversations.schemas import MessageRead


def test_transcript_ids_and_timing():
    transcript = [
        {"text": "First", "offset": 1.25, "duration": 2.5},
        {"text": "Second", "offset": 5},
        {"text": "Third", "offset": 9},
    ]
    context, refs = transcript_context(transcript)
    assert context == transcript_context(json.loads(json.dumps(transcript)))[0]
    assert [(r.start_seconds, r.end_seconds) for r in refs.values()] == [
        (1.25, 3.75),
        (5, 9),
        (9, 9),
    ]
    changed = transcript_context([*transcript, {"text": "New", "offset": 10}])[1]
    assert not refs.keys() & changed.keys()


@pytest.mark.parametrize(
    "timing",
    [
        {},
        {"offset": -1},
        {"offset": True},
        {"offset": float("nan")},
        {"offset": float("inf")},
        {"offset": "10"},
        {"offset": 0, "duration": -1},
        {"offset": 0, "duration": None},
    ],
)
def test_uncitable_text_stays_in_context(timing):
    context, refs = transcript_context([{"text": "Untimed", **timing}])
    assert context == [{"text": "Untimed", "citable": False}]
    assert refs == {}


def test_missing_duration_uses_next_later_valid_offset():
    context, _ = transcript_context(
        [
            {"text": "First", "offset": 5},
            {"text": "Earlier", "offset": 3},
            {"text": "Unknown"},
            {"text": "Later", "offset": 8},
        ]
    )
    assert context[0]["end_seconds"] == 8


@pytest.mark.parametrize("width", [1, 2, 7, 4096])
def test_decoder_arbitrary_boundaries(width):
    parts = [
        {
            "type": "block",
            "text": '# Title\n\n```json\n{"x": "a\\b"}\n```\nक 😀',
            "references": [{"list_item_index": None, "chunk_ids": ["chunk_1"]}],
        },
        {"type": "block", "text": "**Last**", "references": []},
    ]
    payload = json.dumps({"parts": parts})
    decoder = PartsDecoder()
    actual = []
    for offset in range(0, len(payload), width):
        actual.extend(decoder.feed(payload[offset : offset + width]))
    assert [part.model_dump() for part in actual] == parts
    assert decoder.finish().parts == actual


def test_decoder_emits_before_envelope_finishes():
    decoder = PartsDecoder()
    emitted = list(
        decoder.feed('{"parts":[{"type":"block","text":"Ready","references":[]}')
    )
    assert [block.text for block in emitted] == ["Ready"]
    list(decoder.feed("]}"))
    decoder.finish()


@pytest.mark.parametrize(
    "payload",
    [
        '{"parts":[{"type":"block","text":"x","references":[]}]',
        '{"parts":[{"type":"block","text":"x","references":[]}],"extra":1}',
        '{"wrong":[{"type":"block","text":"x","references":[]}]}',
        '{"parts":[{"type":"block","text":"x","text":"y","references":[]}]}',
        '{"parts":[],"parts":[]}',
        '{"parts":[{"type":"block","text":"x","references":[]} {"type":"block"}]}',
        '{"parts":[]} trailing',
        '{"parts":[{"type":"text","text":"x"}]}',
        '{"parts":[{"type":"citation","chunk_id":"c"}]}',
        '{"parts":[{"type":"tool","name":"seek"}]}',
    ],
)
def test_decoder_rejects_invalid_output(payload):
    with pytest.raises(ValueError):
        decoder = PartsDecoder()
        list(decoder.feed(payload))
        decoder.finish()


def test_citation_times_must_be_ordered():
    with pytest.raises(ValidationError):
        CitationPart(type="citation", chunk_id="c", start_seconds=5, end_seconds=2)


def fake_provider(monkeypatch, payload, *, finish="stop", fail=False):
    captured, closed = {}, []

    class Stream:
        def __iter__(self):
            for char in payload:
                yield SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(content=char), finish_reason=None
                        )
                    ]
                )
            if fail:
                raise RuntimeError("provider failed")
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(content=None), finish_reason=finish
                    )
                ]
            )

        def close(self):
            closed.append(True)

    def create(**kwargs):
        captured.update(kwargs)
        return Stream()

    monkeypatch.setattr(
        service,
        "OpenAI",
        lambda **kw: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        ),
    )
    return captured, closed


def run_stream(db_session, *, history=None):
    conversation = Conversation(video_id="abc123DEF45", guest_session_id="guest")
    db_session.add(conversation)
    db_session.commit()
    conversation_id = conversation.id
    events = [
        json.loads(e.removeprefix("data: "))
        for e in service.stream_wiz_response(
            video_title="Test",
            transcript=[{"text": "Source", "offset": 763.5, "duration": 26.5}],
            history=history or [],
            conversation_id=conversation_id,
            db=db_session,
            api_key="test",
        )
    ]
    return events, service.list_messages(db_session, conversation_id)


def test_legacy_history_replays_as_blocks_without_citations(db_session, monkeypatch):
    _, refs = transcript_context(
        [{"text": "Source", "offset": 763.5, "duration": 26.5}]
    )
    chunk_id = next(iter(refs))
    captured, closed = fake_provider(
        monkeypatch,
        json.dumps({"parts": [{"type": "block", "text": "Now", "references": []}]}),
    )
    history = [
        {
            "role": "assistant",
            "content": "Earlier",
            "metadata": {
                "parts_version": 1,
                "parts": [
                    {"type": "text", "text": "Earlier"},
                    refs[chunk_id].model_dump(),
                ],
            },
        }
    ]
    events, _ = run_stream(db_session, history=history)
    assert [event["type"] for event in events] == ["block", "done"]
    assert captured["extra_body"] == {"provider": {"require_parameters": True}}
    assert captured["response_format"]["json_schema"]["strict"] is True
    assert json.loads(captured["messages"][1]["content"])["parts"] == [
        {"type": "block", "text": "Earlier", "references": []}
    ]
    assert closed == [True]


@pytest.mark.parametrize(
    "finish,fail,suffix",
    [
        ("length", False, "]}"),
        (None, False, "]}"),
        ("stop", True, "]}"),
        ("stop", False, ""),
        ("stop", False, '],"extra":true}'),
    ],
)
def test_failed_stream_keeps_emitted_parts_without_persisting(
    db_session, monkeypatch, finish, fail, suffix
):
    fake_provider(
        monkeypatch,
        '{"parts":[{"type":"block","text":"Partial","references":[]}' + suffix,
        finish=finish,
        fail=fail,
    )
    events, messages = run_stream(db_session)
    assert events[0] == {"type": "block", "text": "Partial", "citations": []}
    assert events[-1]["type"] == "error"
    assert not any(e["type"] == "done" for e in events)
    assert messages == []


def test_persistence_failure_never_emits_done(db_session, monkeypatch):
    fake_provider(
        monkeypatch, '{"parts":[{"type":"block","text":"Answer","references":[]}]}'
    )

    def fail(*args, **kwargs):
        raise RuntimeError("storage failed")

    monkeypatch.setattr(service, "save_chat_message", fail)
    events, messages = run_stream(db_session)
    assert events[-1]["type"] == "error"
    assert messages == []


def test_legacy_message_remains_text(db_session):
    conversation = Conversation(video_id="abc123DEF45", user_id=1)
    db_session.add(conversation)
    db_session.commit()
    message = service.save_chat_message(
        db_session, conversation.id, "assistant", "Old [12:43]"
    )
    assert MessageRead.model_validate(message).parts == [
        TextPart(type="text", text="Old [12:43]")
    ]


def test_grouped_passages_and_independent_targets():
    from src.conversations.parts import BlockReference, ModelBlock, resolve_block

    _, refs = transcript_context(
        [
            {"text": "a", "offset": 0, "duration": 4},
            {"text": "b", "offset": 3, "duration": 5},
            {"text": "c", "offset": 13, "duration": 37},
            {"text": "d", "offset": 55, "duration": 10},
            {"text": "e", "offset": 100, "duration": 80},
        ]
    )
    ids = list(refs)
    result = resolve_block(
        ModelBlock(
            type="block",
            text="3. First\n   - Nested\n4. Second",
            references=[
                BlockReference(list_item_index=0, chunk_ids=[*reversed(ids), ids[0]]),
                BlockReference(list_item_index=0, chunk_ids=[ids[1]]),
                BlockReference(list_item_index=1, chunk_ids=ids[:2]),
                BlockReference(list_item_index=2, chunk_ids=[ids[0]]),
                BlockReference(list_item_index=-1, chunk_ids=[ids[0]]),
            ],
        ),
        refs,
    )
    assert len(result.citations) == 2
    assert [(p.start_seconds, p.end_seconds) for p in result.citations[0].passages] == [
        (0, 50),
        (55, 65),
        (100, 180),
    ]
    assert result.citations[0].passages[0].chunk_ids == ids[:3]
    assert result.citations[1].passages[0].chunk_ids == ids[:2]


@pytest.mark.parametrize(
    "text,index,valid",
    [
        ("Paragraph", None, True),
        ("Paragraph", 0, False),
        ("Two\n\nParagraphs", None, False),
        ("# Heading\n\nParagraph", None, False),
        ("> Quote", None, True),
        ("```text\n- Not a list\n```", 0, False),
        ("```text\ncode\n```", None, True),
        ("| a | b |\n|---|---|\n| c | d |", None, True),
    ],
)
def test_reference_targets_preserve_text(text, index, valid):
    from src.conversations.parts import BlockReference, ModelBlock, resolve_block

    _, refs = transcript_context([{"text": "Source", "offset": 1, "duration": 2}])
    block = ModelBlock(
        type="block",
        text=text,
        references=[
            BlockReference(
                list_item_index=index, chunk_ids=[next(iter(refs)), "unknown"]
            )
        ],
    )
    result = resolve_block(block, refs)
    assert result.text == text
    assert bool(result.citations) == valid


@pytest.mark.parametrize("fail", [False, True])
def test_stream_persistence_and_history(db_session, monkeypatch, fail):
    from src.conversations.parts import history_parts, stored_parts

    _, refs = transcript_context(
        [{"text": "Source", "offset": 763.5, "duration": 26.5}]
    )
    key = next(iter(refs))
    block = {
        "type": "block",
        "text": "Answer",
        "references": [{"list_item_index": None, "chunk_ids": [key, "unknown"]}],
    }
    captured, closed = fake_provider(
        monkeypatch, json.dumps({"parts": [block]}), fail=fail
    )
    events, messages = run_stream(db_session)
    assert events[0]["type"] == "block"
    assert events[0]["citations"][0]["passages"] == [
        {"chunk_ids": [key], "start_seconds": 763.5, "end_seconds": 790.0}
    ]
    assert closed == [True]
    if fail:
        assert events[-1]["type"] == "error"
        assert messages == []
    else:
        assert events[-1]["type"] == "done"
        read = MessageRead.model_validate(messages[0])
        assert read.content == "Answer"
        assert read.metadata["parts_version"] == 2
        assert [p.model_dump() for p in read.parts] == events[:-1]
        assert "list_item_index" in captured["messages"][0]["content"]
        parts = stored_parts(read.content, read.metadata)
        assert history_parts(parts, refs)[0]["references"][0]["chunk_ids"] == [key]
        assert history_parts(parts, {})[0]["references"] == []


def test_decoder_atomic_and_model_cannot_supply_times():
    decoder = PartsDecoder()
    block = {
        "type": "block",
        "text": "Answer",
        "references": [{"list_item_index": None, "chunk_ids": ["a"]}],
    }
    prefix = '{"parts":[' + json.dumps(block)
    assert list(decoder.feed(prefix[:-1])) == []
    assert len(list(decoder.feed(prefix[-1:]))) == 1
    list(decoder.feed("]}"))
    decoder.finish()
    block["references"][0]["start_seconds"] = 1
    with pytest.raises(ValueError):
        list(PartsDecoder().feed(json.dumps({"parts": [block]})))


@pytest.mark.asyncio
async def test_route_stream_and_history_contract(client, db_session, monkeypatch):
    from src.videos.models import Video

    video = Video(video_id="abc123DEF45", transcript_available=True, title="Video")
    conversation = Conversation(video_id=video.video_id, guest_session_id="v2-guest")
    db_session.add_all([video, conversation])
    db_session.commit()
    transcript = [{"text": "Source", "offset": 0, "duration": 3}]
    key = next(iter(transcript_context(transcript)[1]))
    fake_provider(
        monkeypatch,
        json.dumps(
            {
                "parts": [
                    {
                        "type": "block",
                        "text": "Answer",
                        "references": [{"list_item_index": None, "chunk_ids": [key]}],
                    }
                ]
            }
        ),
    )
    monkeypatch.setattr(service, "get_transcript_from_s3", lambda _: transcript)
    url = f"/v2/conversations/{conversation.id}/messages"
    headers = {"X-Guest-Session-ID": "v2-guest"}
    response = await client.post(url, headers=headers, json={"message": "Explain"})
    assert response.status_code == 200
    events = [
        json.loads(b.removeprefix("data: "))
        for b in response.text.strip().split("\n\n")
    ]
    assert [e["type"] for e in events] == ["block", "done"]
    history = (await client.get(url, headers=headers)).json()
    assert history[0]["parts"] == [{"type": "text", "text": "Explain"}]
    assert history[1]["parts"] == events[:-1]
    assert history[1]["id"] == events[-1]["message_id"]
    for version in (1, 3):
        invalid = await client.post(
            url, headers=headers, json={"message": "Explain", "parts_version": version}
        )
        assert invalid.status_code == 422
    denied = await client.get(url, headers={"X-Guest-Session-ID": "different"})
    assert denied.status_code == 404


def _block(text, *references):
    from src.conversations.parts import BlockReference, ModelBlock

    return ModelBlock(
        type="block",
        text=text,
        references=[
            BlockReference(list_item_index=index, chunk_ids=ids)
            for index, ids in references
        ],
    )


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Paragraph", ["Paragraph"]),
        ("# Title\n\nBody", ["# Title", "Body"]),
        (
            "Lead\n\n- a\n- b\n\nClosing\n\n> Quote",
            ["Lead", "- a\n- b", "Closing", "> Quote"],
        ),
        (
            "Lead\n\n```py\na\n\nb\n```\n\nClosing",
            ["Lead", "```py\na\n\nb\n```", "Closing"],
        ),
        (
            "Lead\n\n| a | b |\n|---|---|\n| c | d |\n\nClosing",
            ["Lead", "| a | b |\n|---|---|\n| c | d |", "Closing"],
        ),
        (
            "Lead\n\n1. One\n   - nested\n\n   - more\n2. Two\n\nClosing",
            ["Lead", "1. One\n   - nested\n\n   - more\n2. Two", "Closing"],
        ),
        ("One\r\n\r\nTwo", ["One", "Two"]),
    ],
)
def test_split_block_keeps_each_element_whole(text, expected):
    from src.conversations.parts import split_block

    result = split_block(_block(text))
    assert [b.text for b in result.blocks] == expected
    assert result.dropped == []
    if len(expected) == 1:
        assert result.blocks[0].text == text
    else:
        assert "\n\n".join(expected) == text.replace("\r\n", "\n")


def test_split_block_maps_list_item_references_onto_the_lone_list():
    from src.conversations.parts import split_block

    result = split_block(_block("Lead\n\n- a\n- b\n\nClosing", (1, ["x"]), (0, ["y"])))
    assert [
        [(r.list_item_index, r.chunk_ids) for r in b.references] for b in result.blocks
    ] == [
        [],
        [(1, ["x"]), (0, ["y"])],
        [],
    ]
    assert result.dropped == []


@pytest.mark.parametrize(
    "text,index,reason",
    [
        ("Lead\n\n- a\n- b", 2, "index_out_of_range"),
        ("Lead\n\n- a\n- b", -1, "index_out_of_range"),
        ("Lead\n\nClosing", 0, "index_out_of_range"),
        ("- a\n\nMid\n\n1. b", 0, "ambiguous_list"),
        ("# Title\n\n## Subtitle", None, "no_content_part"),
    ],
)
def test_split_block_reports_why_a_reference_was_dropped(text, index, reason):
    from src.conversations.parts import DropReason, split_block

    result = split_block(_block(text, (index, ["x", "y"])))
    assert [(d.reason, d.chunk_ids) for d in result.dropped] == [
        (DropReason(reason), ["x", "y"])
    ]
    assert all(b.references == [] for b in result.blocks)


def test_split_block_attaches_whole_block_reference_to_last_content_part():
    from src.conversations.parts import split_block

    result = split_block(_block("Lead\n\nBody\n\n# Trailing heading", (None, ["x"])))
    assert [bool(b.references) for b in result.blocks] == [False, True, False]
    assert result.blocks[1].references[0].list_item_index is None
    assert result.dropped == []


def test_split_block_leaves_link_reference_definitions_together():
    from src.conversations.parts import DropReason, split_block

    block = _block(
        "See [docs].\n\n- a\n- b\n\n[docs]: https://example.com",
        (0, ["x"]),
        (None, ["y"]),
    )
    result = split_block(block)
    assert result.blocks == [block]
    assert [(d.reason, d.chunk_ids) for d in result.dropped] == [
        (DropReason.LINK_DEFINITIONS, ["x"]),
        (DropReason.LINK_DEFINITIONS, ["y"]),
    ]
    # A definition next to a single element does not need splitting.
    single = _block("See [docs].\n\n[docs]: https://example.com", (None, ["x"]))
    assert split_block(single).blocks == [single]
    assert split_block(single).dropped == []


def test_split_then_resolve_keeps_citations_for_single_block_answer():
    from src.conversations.parts import resolve_block, split_block

    _, refs = transcript_context(
        [
            {"text": "a", "offset": 0, "duration": 4},
            {"text": "b", "offset": 60, "duration": 4},
            {"text": "c", "offset": 120, "duration": 4},
        ]
    )
    first, second, third = refs
    text = (
        "**Jev builds three things.**\n\n"
        "1. A router\n2. A cache\n3. A queue\n\n"
        '> "Ship it"\n\nThat is the summary.'
    )
    result = split_block(
        _block(
            text,
            (0, [first]),
            (2, [third]),
            (None, [second]),
        )
    )
    parts = [resolve_block(b, refs) for b in result.blocks]
    assert [p.text for p in parts] == [
        "**Jev builds three things.**",
        "1. A router\n2. A cache\n3. A queue",
        '> "Ship it"',
        "That is the summary.",
    ]
    assert [[c.list_item_index for c in p.citations] for p in parts] == [
        [],
        [0, 2],
        [],
        [None],
    ]


def test_stream_splits_a_multi_element_block(db_session, monkeypatch, caplog):
    import logging

    from src.conversations.parts import history_parts, stored_parts

    _, refs = transcript_context(
        [{"text": "Source", "offset": 763.5, "duration": 26.5}]
    )
    key = next(iter(refs))
    block = {
        "type": "block",
        "text": "Lead\n\n- One\n- Two\n\nClosing",
        "references": [
            {"list_item_index": 0, "chunk_ids": [key]},
            {"list_item_index": 1, "chunk_ids": [key, "unknown"]},
            {"list_item_index": 5, "chunk_ids": [key]},
            {"list_item_index": None, "chunk_ids": [key]},
        ],
    }
    fake_provider(monkeypatch, json.dumps({"parts": [block]}))
    with caplog.at_level(logging.INFO, logger=service.logger.name):
        events, messages = run_stream(db_session)
    assert [e["type"] for e in events] == ["block"] * 3 + ["done"]
    assert [e["text"] for e in events[:3]] == ["Lead", "- One\n- Two", "Closing"]
    passage = {"chunk_ids": [key], "start_seconds": 763.5, "end_seconds": 790.0}
    assert [e["citations"] for e in events[:3]] == [
        [],
        [
            {"list_item_index": 0, "passages": [passage]},
            {"list_item_index": 1, "passages": [passage]},
        ],
        [{"list_item_index": None, "passages": [passage]}],
    ]
    read = MessageRead.model_validate(messages[0])
    assert read.content == "Lead\n\n- One\n- Two\n\nClosing"
    assert [p.model_dump() for p in read.parts] == events[:-1]
    replay = history_parts(stored_parts(read.content, read.metadata), refs)
    assert [
        [(r["list_item_index"], r["chunk_ids"]) for r in part["references"]]
        for part in replay
    ] == [[], [(0, [key]), (1, [key])], [(None, [key])]]
    assert [
        r.getMessage()
        for r in caplog.records
        if r.getMessage().startswith("Wiz structure:")
    ] == [
        "Wiz structure: model=%s blocks_in=1 blocks_out=3 blocks_split=1 "
        "referenced=2 kept=1 dropped_ambiguous_list=0 "
        "dropped_index_out_of_range=1 dropped_no_content_part=0 "
        "dropped_link_definitions=0" % settings.wiz_model
    ]


def test_prompt_includes_worked_example_and_transcript():
    transcript = [{"text": "Source", "offset": 0, "duration": 3}]
    prompt = service.build_system_instruction("Video", transcript)
    assert prompt.startswith(
        'You are Wiz, an AI assistant dedicated to this specific video: "Video".'
    )
    assert '{"parts": [' in prompt
    assert '"list_item_index": 0' in prompt and '"list_item_index": 1' in prompt
    assert '"list_item_index": null' in prompt
    assert prompt.count("Response structure:") == 1
    assert "Source" in prompt and "{transcript}" not in prompt
