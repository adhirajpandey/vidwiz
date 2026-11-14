import json
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.exc import OperationalError

from src.ask import search as ask_search
from src.ask import tools
from src.ask.sources import Source
from src.auth.models import User
from src.config import settings
from src.library.models import LibraryItem
from src.moments.models import CaptureSource, Moment
from src.search.models import TranscriptChunk
from src.shared import embeddings
from src.videos.models import TranscriptStatus, Video

KOLKATA = "Asia/Kolkata"


def vector(axis: int) -> list[float]:
    values = [0.0] * 1024
    values[axis] = 1.0
    return values


def utc(*parts) -> datetime:
    return datetime(*parts, tzinfo=timezone.utc)


@pytest.fixture
def query_vector(monkeypatch):
    """The query embeds along axis 0 unless a test changes it."""
    state = {"vector": vector(0), "calls": []}

    def embed_query(text):
        state["calls"].append(text)
        if isinstance(state["vector"], Exception):
            raise state["vector"]
        return state["vector"], 3

    monkeypatch.setattr(embeddings, "embed_query", embed_query)
    return state


@pytest.fixture
def other_user(db_session):
    other = User(email="other@example.com", name="Other", credits_balance=0)
    db_session.add(other)
    db_session.flush()
    return other


def add_video(db, video_id, title, uploader=None, summary=None, **fields):
    video = Video(
        video_id=video_id,
        title=title,
        video_metadata={"uploader": uploader} if uploader else {},
        summary=summary,
        transcript_status=fields.pop("transcript_status", TranscriptStatus.READY),
        **fields,
    )
    db.add(video)
    db.flush()
    return video


def save(db, user, video_id, added_at):
    db.add(LibraryItem(user_id=user.id, video_id=video_id, added_at=added_at))
    db.flush()


def add_chunks(db, video_id, texts, embedded=None):
    """One passage per text, 60 seconds apart; `embedded` maps index to axis."""
    chunks = [
        TranscriptChunk(
            video_id=video_id,
            idx=index,
            start_seconds=index * 60,
            end_seconds=index * 60 + 45,
            text=text,
            embedding=vector(embedded[index])
            if embedded and index in embedded
            else None,
        )
        for index, text in enumerate(texts)
    ]
    db.add_all(chunks)
    db.flush()
    return chunks


def add_moment(db, user, video_id, at, created_at, **fields):
    axis = fields.pop("axis", None)
    moment = Moment(
        user_id=user.id,
        video_id=video_id,
        at_seconds=at,
        source=CaptureSource.WEB,
        created_at=created_at,
        embedding=vector(axis) if axis is not None else None,
        **fields,
    )
    db.add(moment)
    db.flush()
    return moment


@pytest.fixture
def library(db_session, user, other_user):
    db = db_session
    add_video(
        db,
        "aaaaaaaaaaa",
        "Indexes talk",
        "Hussein Nasser",
        "Composite indexes and column order. " + "x" * 300,
    )
    add_video(db, "bbbbbbbbbbb", "Deep work", "Cal Newport", "Focus without phones.")
    add_video(
        db,
        "ccccccccccc",
        "Punctuation channel",
        "!!!",
        transcript_status=TranscriptStatus.PENDING,
    )
    # Saved only by the other user, with the same words as the user's videos.
    add_video(db, "ddddddddddd", "Other indexes", "Hussein Nasser", "Indexes too.")
    # Not saved by anyone.
    add_video(db, "eeeeeeeeeee", "Unsaved indexes", "Hussein Nasser")

    save(db, user, "aaaaaaaaaaa", utc(2026, 11, 1, 19, 0))  # Nov 2 00:30 in Kolkata
    save(db, user, "bbbbbbbbbbb", utc(2026, 10, 5, 12, 0))
    save(db, user, "ccccccccccc", utc(2026, 9, 1, 12, 0))
    save(db, other_user, "ddddddddddd", utc(2026, 11, 3, 12, 0))

    chunks = {
        "aaaaaaaaaaa": add_chunks(
            db,
            "aaaaaaaaaaa",
            [
                "Today we talk about databases and indexes.",
                "Composite indexes need the right column order.",
                "The leftmost column of an index is used first.",
                "Covering indexes avoid a table lookup.",
            ],
            embedded={0: 1, 1: 1, 2: 1},
        ),
        "bbbbbbbbbbb": add_chunks(
            db,
            "bbbbbbbbbbb",
            [
                "Deep focus needs long blocks of time.",
                "Put your phone in another room.",
            ],
            embedded={1: 0},
        ),
        "ddddddddddd": add_chunks(
            db, "ddddddddddd", ["Indexes and column order again."], embedded={0: 0}
        ),
        "eeeeeeeeeee": add_chunks(
            db, "eeeeeeeeeee", ["Indexes in an unsaved video."], embedded={0: 0}
        ),
    }
    moments = {
        "index": add_moment(
            db,
            user,
            "aaaaaaaaaaa",
            70,
            utc(2026, 11, 1, 19, 0),
            note="Index column ordering",
            ai_text="Put the most selective column first",
            quote="the right column order",
        ),
        "focus": add_moment(
            db, user, "bbbbbbbbbbb", 65, utc(2026, 11, 1, 18, 0), ai_text="Phone away"
        ),
        "other": add_moment(
            db,
            other_user,
            "ddddddddddd",
            0,
            utc(2026, 11, 1, 19, 0),
            note="Index column ordering",
            axis=0,
        ),
    }
    return {"chunks": chunks, "moments": moments}


def context(db, user, time_zone="UTC", seen=()):
    return tools.ToolContext(db, user.id, time_zone, set(seen))


def ids(sources):
    return [source.source_id for source in sources]


# ---- search ----


def test_search_ranks_keywords_inside_the_users_library(
    db_session, user, library, query_vector
):
    query_vector["vector"] = embeddings.EmbeddingError("down")

    found = ask_search.search(
        db_session, user.id, "What is the column order of an index?", time_zone=KOLKATA
    )

    chunks, moment = library["chunks"]["aaaaaaaaaaa"], library["moments"]["index"]
    # The moment's weight puts it first; the per-video cap keeps two sources.
    assert ids(found.sources) == [f"m{moment.id}", f"c{chunks[1].id}"]
    first = found.sources[0]
    assert first.kind == "moment"
    assert first.text == (
        "User note: Index column ordering\n"
        "AI line: Put the most selective column first\n"
        "Said in the video: the right column order"
    )
    assert first.captured == date(2026, 11, 2)
    assert first.channel == "Hussein Nasser"
    assert first.citation().video_id == "aaaaaaaaaaa"
    passage = found.sources[1]
    assert (passage.kind, passage.start_seconds, passage.end_seconds) == (
        "transcript",
        60,
        105,
    )
    assert passage.video_title == "Indexes talk"
    assert [video.video_id for video in found.videos] == ["aaaaaaaaaaa"]
    assert (
        found.videos[0].summary
        == ("Composite indexes and column order. " + "x" * 300)[:200]
    )


def test_search_drops_stop_words_and_caps_terms():
    assert ask_search.query_terms("What is the Index of my DB?") == ["index", "db"]
    assert len(ask_search.query_terms(" ".join(f"w{n}" for n in range(30)))) == 20


def test_search_never_returns_other_users_or_unsaved_videos(
    db_session, user, other_user, library, query_vector
):
    found = ask_search.search(db_session, user.id, "indexes column order")

    assert found.sources and found.videos
    assert {source.video_id for source in found.sources} <= {
        "aaaaaaaaaaa",
        "bbbbbbbbbbb",
    }
    assert f"m{library['moments']['other'].id}" not in ids(found.sources)
    assert {video.video_id for video in found.videos} <= {
        "aaaaaaaaaaa",
        "bbbbbbbbbbb",
        "ccccccccccc",
    }

    other = ask_search.search(db_session, other_user.id, "indexes column order")
    assert {source.video_id for source in other.sources} == {"ddddddddddd"}


def test_search_video_ids_limit_passages_and_moments(
    db_session, user, library, query_vector
):
    found = ask_search.search(
        db_session, user.id, "phone column", video_ids=["bbbbbbbbbbb"]
    )
    assert {source.video_id for source in found.sources} == {"bbbbbbbbbbb"}

    # Ids outside the user's library match nothing, keyword or embedding.
    outside = ask_search.search(
        db_session,
        user.id,
        "indexes column order",
        video_ids=["ddddddddddd", "eeeeeeeeeee"],
    )
    assert outside.sources == []


def test_search_uses_embeddings_and_skips_null_vectors(
    db_session, user, library, query_vector
):
    # No keyword matches "attention"; only embedded rows along axis 0 can match.
    found = ask_search.search(db_session, user.id, "attention")

    phone = library["chunks"]["bbbbbbbbbbb"][1]
    assert ids(found.sources)[0] == f"c{phone.id}"
    unembedded = {
        f"c{library['chunks']['aaaaaaaaaaa'][3].id}",
        f"c{library['chunks']['bbbbbbbbbbb'][0].id}",
        f"m{library['moments']['index'].id}",
        f"m{library['moments']['focus'].id}",
    }
    assert not unembedded & set(ids(found.sources))
    assert query_vector["calls"] == ["attention"]


def test_search_falls_back_to_keywords_when_embedding_fails(
    db_session, user, library, query_vector
):
    query_vector["vector"] = embeddings.EmbeddingError("HTTP 500")

    assert ask_search.search(db_session, user.id, "attention").sources == []
    found = ask_search.search(db_session, user.id, "phone")
    assert ids(found.sources) == [
        f"m{library['moments']['focus'].id}",
        f"c{library['chunks']['bbbbbbbbbbb'][1].id}",
    ]


def test_search_without_api_key_uses_keywords(db_session, user, library, monkeypatch):
    # The real embedding path, which refuses before any request without a key.
    monkeypatch.setattr(settings, "openrouter_api_key", None)

    found = ask_search.search(db_session, user.id, "deep work")

    assert found.sources
    assert [video.video_id for video in found.videos] == ["bbbbbbbbbbb"]


def test_search_blank_query_matches_nothing(db_session, user, library, query_vector):
    assert ask_search.search(db_session, user.id, "   ").sources == []
    assert query_vector["calls"] == []


def test_search_tolerates_punctuation_and_stop_words(
    db_session, user, library, query_vector
):
    query_vector["vector"] = embeddings.EmbeddingError("down")

    assert ask_search.search(db_session, user.id, "what is it?").sources == []
    found = ask_search.search(db_session, user.id, "a_b c++ 'phone' :* & | !")
    assert found.sources


def test_fusion_and_per_video_cap():
    def source(source_id, video_id):
        return Source(source_id, video_id, None, "transcript", 0, 0, "")

    a, b, c, d = (
        source("c1", "v1"),
        source("c2", "v1"),
        source("c3", "v1"),
        source("c4", "v2"),
    )
    key = lambda item: item.source_id  # noqa: E731
    # In both rankings beats first in one.
    fused = ask_search.fuse([a, d, c], [d, b, c], key=key)
    assert ids(fused) == ["c4", "c3", "c1", "c2"]
    assert ids(ask_search.cap_per_video(fused)) == ["c4", "c3", "c1"]


def test_search_caps_sources_per_video(db_session, user, library, query_vector):
    query_vector["vector"] = vector(1)

    found = ask_search.search(db_session, user.id, "indexes", limit=8)

    per_video = [source.video_id for source in found.sources]
    assert per_video.count("aaaaaaaaaaa") == 2


def test_search_cards_fuse_keyword_and_embedding(
    db_session, user, library, query_vector
):
    add_video(db_session, "fffffffffff", "Sleep").card_embedding = vector(0)
    save(db_session, user, "fffffffffff", utc(2026, 11, 5))
    other = db_session.query(Video).filter_by(video_id="ddddddddddd").one()
    other.card_embedding = vector(0)
    db_session.flush()

    found = ask_search.search(db_session, user.id, "deep")

    # The embedding-only card and the keyword-only card both appear; the other
    # user's embedded card does not.
    assert {video.video_id for video in found.videos} == {
        "bbbbbbbbbbb",
        "fffffffffff",
    }


# ---- find_videos and library_stats ----


def run(name, arguments, ctx):
    return tools.run_tool(name, arguments, ctx)


def test_find_videos_lists_the_users_library_newest_first(db_session, user, library):
    result = run("find_videos", {}, context(db_session, user, KOLKATA)).result

    assert result["total"] == 3
    assert [video["video_id"] for video in result["videos"]] == [
        "aaaaaaaaaaa",
        "bbbbbbbbbbb",
        "ccccccccccc",
    ]
    first = result["videos"][0]
    assert first["saved"] == "2026-11-02"
    assert first["channel"] == "Hussein Nasser"
    assert first["has_transcript"] is True
    assert len(first["summary"]) == 200
    assert result["videos"][2]["has_transcript"] is False


def test_find_videos_saved_dates_use_the_local_time_zone(db_session, user, library):
    def found(time_zone, **arguments):
        result = run("find_videos", arguments, context(db_session, user, time_zone))
        return [video["video_id"] for video in result.result["videos"]]

    # Saved at 19:00 UTC on Nov 1, which is Nov 2 in Kolkata.
    assert found(KOLKATA, saved_from="2026-11-02") == ["aaaaaaaaaaa"]
    assert found(KOLKATA, saved_to="2026-11-01") == ["bbbbbbbbbbb", "ccccccccccc"]
    assert found("UTC", saved_from="2026-11-02") == []
    assert found("UTC", saved_from="2026-11-01", saved_to="2026-11-01") == [
        "aaaaaaaaaaa"
    ]


def test_find_videos_matches_channels_loosely(db_session, user, library):
    ctx = context(db_session, user)

    def found(**arguments):
        return run("find_videos", arguments, ctx).result

    assert [
        video["video_id"] for video in found(channel="hussein-nasser")["videos"]
    ] == ["aaaaaaaaaaa"]
    assert found(channel="Cal Newport Podcast")["total"] == 1
    assert found(channel="Indexes", title_contains="talk").get("videos") is None
    assert found(title_contains="DEEP")["total"] == 1
    assert found(title_contains="%")["total"] == 0

    close = found(channel="Husein Naser")
    assert "videos" not in close
    assert "['Hussein Nasser']" in close["note"]


def test_channel_with_an_empty_normal_form_matches_nothing(db_session, user, library):
    ctx = context(db_session, user)
    # The "!!!" uploader normalises to nothing and must not match every channel.
    assert tools.match_channels(["!!!", "Cal Newport"], "Cal") == (["Cal Newport"], [])
    assert tools.match_channels(["!!!", "Cal Newport"], "???") == ([], [])
    result = run("find_videos", {"channel": "!!!"}, ctx).result
    assert "videos" not in result and "note" in result
    result = run("find_videos", {"channel": "Nasser"}, ctx).result
    assert [video["video_id"] for video in result["videos"]] == ["aaaaaaaaaaa"]
    # An empty channel is treated as no filter.
    assert run("find_videos", {"channel": " "}, ctx).result["total"] == 3


def test_library_stats_counts_and_groups(db_session, user, other_user, library):
    ctx = context(db_session, user, KOLKATA)

    assert run("library_stats", {}, ctx).result == {"video_count": 3}
    assert run(
        "library_stats", {"group_by": "none", "channel": "nasser"}, ctx
    ).result == {"video_count": 1}
    assert run("library_stats", {"group_by": "channel"}, ctx).result == {
        "groups": [
            {"name": "!!!", "videos": 1},
            {"name": "Cal Newport", "videos": 1},
            {"name": "Hussein Nasser", "videos": 1},
        ]
    }
    months = run("library_stats", {"group_by": "month"}, ctx).result["groups"]
    assert {group["name"] for group in months} == {"2026-11", "2026-10", "2026-09"}
    assert (
        run("library_stats", {"channel": "zzzz"}, ctx)
        .result["note"]
        .startswith("No channel matches")
    )
    other = run("library_stats", {}, context(db_session, other_user)).result
    assert other == {"video_count": 1}


# ---- moments_in ----


def test_moments_in_uses_local_dates_and_the_users_moments(db_session, user, library):
    ctx = context(db_session, user, KOLKATA)
    index, focus = library["moments"]["index"], library["moments"]["focus"]

    # 19:00 UTC on Nov 1 is Nov 2 in Kolkata; 18:00 UTC is 23:30 on Nov 1.
    nov2 = run("moments_in", {"since": "2026-11-02", "until": "2026-11-02"}, ctx)
    assert nov2.result == {
        "total_moments": 1,
        "video_count": 1,
        "videos": [
            {
                "title": "Indexes talk",
                "video_id": "aaaaaaaaaaa",
                "moment_count": 1,
                "moments": [
                    {
                        "id": f"m{index.id}",
                        "at_seconds": 70,
                        "text": "Index column ordering",
                    }
                ],
            }
        ],
    }
    assert ids(nov2.sources) == [f"m{index.id}"]
    assert nov2.sources[0].captured == date(2026, 11, 2)

    nov1 = run("moments_in", {"since": "2026-11-01", "until": "2026-11-01"}, ctx)
    assert ids(nov1.sources) == [f"m{focus.id}"]
    assert nov1.result["videos"][0]["moments"][0]["text"] == "Phone away"


def test_moments_in_caps_listed_moments_and_their_sources(db_session, user, library):
    for second in range(8):
        add_moment(
            db_session,
            user,
            "ccccccccccc",
            second,
            utc(2026, 8, 1, 10, second),
            quote="q" * 300,
        )

    ctx = context(db_session, user)
    result = run("moments_in", {"since": "2026-08-01", "until": "2026-08-01"}, ctx)

    video = result.result["videos"][0]
    assert result.result["total_moments"] == 8
    assert video["moment_count"] == 8
    assert len(video["moments"]) == 6
    assert video["moments"][0]["text"] == "q" * 160
    # Only the listed moments are sources, and only they become fetchable.
    shown = [moment["id"] for moment in video["moments"]]
    assert ids(result.sources) == shown
    assert ctx.seen_ids == set(shown)


def test_moments_in_skips_moments_outside_the_library(db_session, user, library):
    # The user owns a moment on a video they never saved.
    stray = add_moment(
        db_session, user, "eeeeeeeeeee", 0, utc(2026, 11, 1, 12), note="Stray"
    )

    result = run(
        "moments_in",
        {"since": "2026-11-01", "until": "2026-11-01"},
        context(db_session, user),
    )

    assert f"m{stray.id}" not in ids(result.sources)
    assert {video["video_id"] for video in result.result["videos"]} == {
        "aaaaaaaaaaa",
        "bbbbbbbbbbb",
    }


# ---- fetch ----


def test_fetch_returns_a_passage_with_its_neighbours(db_session, user, library):
    chunks = library["chunks"]["aaaaaaaaaaa"]
    seen = {f"c{chunk.id}" for chunk in chunks}
    ctx = context(db_session, user, seen=seen)

    middle = run("fetch", {"source_id": f"c{chunks[1].id}"}, ctx)
    assert middle.result["status"] == "ok"
    assert [p["id"] for p in middle.result["passages"]] == [
        f"c{chunk.id}" for chunk in chunks[:3]
    ]
    assert ids(middle.sources) == [f"c{chunk.id}" for chunk in chunks[:3]]
    assert middle.result["passages"][0]["end_seconds"] == 45

    first = run("fetch", {"source_id": f"c{chunks[0].id}"}, ctx)
    assert ids(first.sources) == [f"c{chunk.id}" for chunk in chunks[:2]]


def test_fetch_moment_returns_its_parts_and_nearest_passages(db_session, user, library):
    index = library["moments"]["index"]
    chunks = library["chunks"]["aaaaaaaaaaa"]
    ctx = context(db_session, user, seen={f"m{index.id}"})

    result = run("fetch", {"source_id": f"m{index.id}"}, ctx)

    assert result.result["moment"] == {
        "id": f"m{index.id}",
        "at_seconds": 70,
        "user_note": "Index column ordering",
        "ai_line": "Put the most selective column first",
        "quote": "the right column order",
    }
    # 70 seconds is nearest the passage at 60.
    assert ids(result.sources) == [f"c{chunk.id}" for chunk in chunks[:3]]

    bare = add_moment(db_session, user, "ccccccccccc", 5, utc(2026, 9, 2), note="n")
    ctx.seen_ids.add(f"m{bare.id}")
    result = run("fetch", {"source_id": f"m{bare.id}"}, ctx)
    assert result.result["status"] == "transcript_unavailable"
    assert result.sources == []


def test_fetch_reads_only_seen_ids_of_the_user(db_session, user, library):
    chunk = library["chunks"]["aaaaaaaaaaa"][0]
    other_chunk = library["chunks"]["ddddddddddd"][0]
    other_moment = library["moments"]["other"]

    unseen = run("fetch", {"source_id": f"c{chunk.id}"}, context(db_session, user))
    assert unseen.result == {"error": "Use a source ID already returned by a tool."}
    assert unseen.sources == []

    # Even when listed as seen, another user's rows are not read.
    ctx = context(db_session, user, seen={f"c{other_chunk.id}", f"m{other_moment.id}"})
    for source_id in ctx.seen_ids:
        result = run("fetch", {"source_id": source_id}, ctx)
        assert result.result == {"error": "Source no longer available."}

    assert "error" in run("fetch", {"source_id": "x1"}, ctx).result


# ---- run_tool ----


def test_search_tool_returns_results_and_sources(
    db_session, user, library, query_vector
):
    result = run(
        "search",
        json.dumps({"query": "phone", "video_ids": ["bbbbbbbbbbb"]}),
        context(db_session, user),
    )

    assert [item["id"] for item in result.result["results"]] == ids(result.sources)
    first = result.result["results"][0]
    assert first["video_id"] == "bbbbbbbbbbb"
    assert first["channel"] == "Cal Newport"
    assert result.result["videos"][0]["video_id"] == "bbbbbbbbbbb"
    json.dumps(result.result)


def test_search_then_fetch_on_one_context(db_session, user, library, query_vector):
    ctx = context(db_session, user)

    found = run("search", {"query": "phone", "video_ids": ["bbbbbbbbbbb"]}, ctx)
    assert ctx.seen_ids == set(ids(found.sources))
    passage = next(s for s in found.sources if s.kind == "transcript")

    fetched = run("fetch", {"source_id": passage.source_id}, ctx)

    assert fetched.result["status"] == "ok"
    assert passage.source_id in ids(fetched.sources)
    # Passages fetch returns are fetchable too; failed calls add nothing.
    assert set(ids(fetched.sources)) <= ctx.seen_ids
    before = set(ctx.seen_ids)
    run("fetch", {"source_id": "c999999"}, ctx)
    assert ctx.seen_ids == before


def test_run_tool_reports_errors_without_raising(
    db_session, user, library, monkeypatch
):
    ctx = context(db_session, user)

    assert run("delete_everything", {}, ctx).result["error"].startswith("Unknown")
    assert "Invalid arguments" in run("search", "{not json", ctx).result["error"]
    assert "Invalid arguments" in run("search", "[1]", ctx).result["error"]
    for falsy in ("[]", "false", "0", '""x', [], False, 0):
        assert "Invalid arguments" in run("find_videos", falsy, ctx).result["error"]
    for empty in (None, "", "  ", "null", '""', {}):
        assert run("find_videos", empty, ctx).result["total"] == 3
    assert "query" in run("search", {}, ctx).result["error"]
    assert (
        "since"
        in run("moments_in", {"since": "soon", "until": "2026-11-01"}, ctx).result[
            "error"
        ]
    )
    assert (
        "error"
        in run("moments_in", {"since": "2026-11-02", "until": "2026-11-01"}, ctx).result
    )
    assert "error" in run("library_stats", {"group_by": "year"}, ctx).result
    assert "error" in run("fetch", {"source_id": "c1; drop"}, ctx).result

    rollbacks = []
    monkeypatch.setattr(db_session, "rollback", lambda: rollbacks.append(True))

    def broken(*_args, **_kwargs):
        raise OperationalError("select", {}, Exception("connection lost"))

    monkeypatch.setattr(ask_search, "search", broken)
    result = run("search", {"query": "phone"}, ctx)
    assert result.result == {"error": "search failed."}
    assert result.sources == []
    assert rollbacks == [True]

    monkeypatch.setattr(ask_search, "search", lambda *_a, **_k: 1 / 0)
    assert run("search", {"query": "phone"}, ctx).result == {"error": "search failed."}
    assert rollbacks == [True]


def test_tool_specs_cover_every_tool():
    names = [spec["function"]["name"] for spec in tools.TOOL_SPECS]
    assert names == ["find_videos", "search", "moments_in", "library_stats", "fetch"]
    for spec in tools.TOOL_SPECS:
        assert spec["type"] == "function"
        assert spec["function"]["parameters"]["type"] == "object"
        json.dumps(spec)
