import pytest

from src import transcripts
from src.library.models import LibraryItem
from src.moments import service as moments_service
from src.moments.schemas import CaptureCreate
from src.search import service as search_service
from src.search.chunks import replace_chunks
from src.search.models import TranscriptChunk
from src.tests.test_moments import auth_headers
from src.videos.models import TranscriptStatus, Video

TRANSCRIPT = [
    {"text": "Today we talk about databases.", "offset": 0, "duration": 5},
    {
        "text": "Composite indexes need the right column order.",
        "offset": 20,
        "duration": 6,
    },
    {"text": "The leftmost column is used first.", "offset": 30, "duration": 5},
    {
        "text": "Now something about deep focus and distraction.",
        "offset": 60,
        "duration": 6,
    },
    {"text": "Put your phone in another room.", "offset": 70, "duration": 4},
]


def test_chunk_transcript_groups_by_time():
    chunks = transcripts.chunk_transcript(
        TRANSCRIPT + [{"text": "  ", "offset": 80}, {"text": "bad", "offset": "x"}]
    )

    assert chunks == [
        (
            0,
            35,
            "Today we talk about databases. Composite indexes need the right "
            "column order. The leftmost column is used first.",
        ),
        (
            60,
            74,
            "Now something about deep focus and distraction. Put your phone in another room.",
        ),
    ]


def test_replace_chunks_replaces_previous_rows(db_session):
    db_session.add(Video(video_id="aaaaaaaaaaa", title="DB"))
    db_session.flush()

    assert replace_chunks(db_session, "aaaaaaaaaaa", TRANSCRIPT) == 2
    assert replace_chunks(db_session, "aaaaaaaaaaa", TRANSCRIPT[:1]) == 1
    db_session.flush()

    rows = db_session.query(TranscriptChunk).filter_by(video_id="aaaaaaaaaaa").all()
    assert [(row.idx, row.text) for row in rows] == [
        (0, "Today we talk about databases.")
    ]


@pytest.fixture
def library(db_session, user):
    db_session.add_all(
        [
            Video(video_id="aaaaaaaaaaa", title="Indexes talk"),
            Video(video_id="bbbbbbbbbbb", title="Not saved"),
        ]
    )
    db_session.flush()
    db_session.add(LibraryItem(user_id=user.id, video_id="aaaaaaaaaaa"))
    replace_chunks(db_session, "aaaaaaaaaaa", TRANSCRIPT)
    replace_chunks(db_session, "bbbbbbbbbbb", TRANSCRIPT)
    moment, _ = moments_service.capture(
        db_session,
        user.id,
        CaptureCreate(
            video="aaaaaaaaaaa", at=25, note="Index column ordering", ai=False
        ),
    )
    moment.quote_start_seconds = 10
    db_session.flush()
    return moment


@pytest.mark.asyncio
async def test_search_ranks_moments_and_passages_with_highlights(
    client, db_session, user, library
):
    response = await client.get(
        "/v2/search?q=index%20column", headers=auth_headers(user)
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["match"] == "exact"
    kinds = [result["kind"] for result in payload["results"]]
    # The user's moment outranks the transcript passage, and unsaved videos
    # never appear.
    assert kinds == ["moment", "passage"]
    moment, passage = payload["results"]
    assert moment["moment"]["id"] == library.id
    assert moment["start_seconds"] == 25
    assert passage["video"]["video_id"] == "aaaaaaaaaaa"
    assert passage["start_seconds"] == 0
    assert passage["video"]["thumbnail_url"].endswith("/aaaaaaaaaaa/mqdefault.jpg")
    highlighted = {
        part["text"].lower() for part in passage["snippet"] if part["highlight"]
    }
    assert {"indexes", "column"} <= highlighted


@pytest.mark.asyncio
async def test_search_prefix_and_stemming(client, db_session, user, library):
    response = await client.get("/v2/search?q=distract", headers=auth_headers(user))

    results = response.json()["results"]
    assert [result["start_seconds"] for result in results] == [60]


@pytest.mark.asyncio
async def test_search_falls_back_to_fuzzy_for_typos(client, db_session, user, library):
    response = await client.get("/v2/search?q=ordring", headers=auth_headers(user))

    payload = response.json()
    assert payload["match"] == "fuzzy"
    assert payload["results"][0]["kind"] == "moment"


@pytest.mark.asyncio
async def test_search_none_and_video_filter_and_privacy(
    client, db_session, user, library
):
    from src.auth import service as auth_service

    none = await client.get("/v2/search?q=zebra%20quantum", headers=auth_headers(user))
    assert none.json()["match"] == "none"
    assert none.json()["results"] == []

    filtered = await client.get(
        "/v2/search?q=column&video_id=bbbbbbbbbbb", headers=auth_headers(user)
    )
    assert filtered.json()["results"] == []

    other = auth_service.create_user(db_session, "x@example.com", "X", "pw123456")
    theirs = await client.get("/v2/search?q=column", headers=auth_headers(other))
    assert theirs.json()["match"] == "none"


@pytest.mark.asyncio
async def test_search_pagination_and_validation(client, db_session, user, library):
    first = await client.get(
        "/v2/search?q=column&per_page=1", headers=auth_headers(user)
    )
    second = await client.get(
        "/v2/search?q=column&per_page=1&page=2", headers=auth_headers(user)
    )
    assert first.json()["has_more"] is True
    assert second.json()["has_more"] is False
    assert first.json()["results"][0] != second.json()["results"][0]

    symbols = await client.get("/v2/search?q=%2B%2B", headers=auth_headers(user))
    assert symbols.status_code == 400


def test_any_mode_matches_partial_terms(db_session, user, library):
    hits = search_service.find(db_session, user.id, "phone database", mode="any")
    assert {hit.result.start_seconds for hit in hits} >= {0, 60}
    assert search_service.find(db_session, user.id, "phone database") == []


def test_backfill_chunks_resumes_and_skips_missing(db_session, monkeypatch):
    from src import database
    from src.management import backfill

    db_session.add_all(
        [
            Video(
                video_id="aaaaaaaaaaa",
                title="A",
                transcript_status=TranscriptStatus.READY,
            ),
            Video(
                video_id="bbbbbbbbbbb",
                title="B",
                transcript_status=TranscriptStatus.READY,
            ),
            Video(
                video_id="ccccccccccc",
                title="C",
                transcript_status=TranscriptStatus.PENDING,
            ),
        ]
    )
    db_session.flush()

    class Session:
        def __getattr__(self, name):
            return getattr(db_session, name)

        def close(self):
            pass

    loads = []

    def load(video_id):
        loads.append(video_id)
        return TRANSCRIPT if video_id == "aaaaaaaaaaa" else None

    monkeypatch.setattr(database, "SessionLocal", Session)
    monkeypatch.setattr(transcripts, "load_transcript", load)

    backfill.backfill_chunks(missing_only=False)
    assert (
        db_session.query(TranscriptChunk).filter_by(video_id="aaaaaaaaaaa").count() == 2
    )
    assert sorted(loads) == ["aaaaaaaaaaa", "bbbbbbbbbbb"]

    loads.clear()
    backfill.backfill_chunks(missing_only=True)
    assert loads == ["bbbbbbbbbbb"]
