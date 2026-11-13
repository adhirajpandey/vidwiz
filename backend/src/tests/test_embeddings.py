from datetime import datetime, timezone

import pytest
import requests
from sqlalchemy import func, select, update

from src import database
from src.config import settings
from src.internal import service as internal_service
from src.management import backfill, sweep
from src.moments import service as moments_service
from src.moments.models import CaptureSource, Moment
from src.search import embeddings as upkeep
from src.search.models import TranscriptChunk
from src.shared import embeddings
from src.videos import service as videos_service
from src.videos.models import Video

# Captured at import, before the autouse fixture blocks it.
REAL_REQUEST = embeddings._request
VECTOR = [0.5] * 1024


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status_code = status
        self.ok = status < 400

    def json(self):
        return self.payload


@pytest.fixture
def api(monkeypatch):
    """Fake OpenRouter embeddings endpoint; records each request."""
    monkeypatch.setattr(embeddings, "_request", REAL_REQUEST)
    monkeypatch.setattr(settings, "openrouter_api_key", "test-openrouter-key")
    calls = []

    def post(url, json, headers, timeout):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        data = [
            {"index": index, "embedding": [float(index)] * 4096}
            for index in range(len(json["input"]))
        ]
        # Out of order, to check vectors follow their index.
        return FakeResponse(
            {"data": list(reversed(data)), "usage": {"total_tokens": 7}}
        )

    monkeypatch.setattr(embeddings.requests, "post", post)
    return calls


def test_embed_documents_batches_clips_and_truncates(api):
    texts = [f"text {index}" for index in range(49)] + ["x" * 7000]

    vectors, tokens = embeddings.embed_documents(texts)

    assert len(vectors) == 50 and tokens == 14
    assert all(len(vector) == 1024 for vector in vectors)
    assert vectors[1] == [1.0] * 1024
    assert [len(call["json"]["input"]) for call in api] == [48, 2]
    first = api[0]
    assert first["url"] == f"{settings.openrouter_base_url}/embeddings"
    assert first["json"]["model"] == "qwen/qwen3-embedding-8b"
    assert first["json"]["provider"] == {
        "order": ["Nebius", "DeepInfra"],
        "allow_fallbacks": False,
    }
    assert first["json"]["input"][0] == "text 0"
    assert first["headers"]["Authorization"] == "Bearer test-openrouter-key"
    assert first["timeout"] == 20
    assert api[1]["json"]["input"][1] == "x" * 6000


def test_embed_query_adds_the_instruction(api):
    vector, tokens = embeddings.embed_query("what is a composite index?")

    assert len(vector) == 1024 and tokens == 7
    assert api[0]["json"]["input"] == [
        "Instruct: Given a question, retrieve transcript passages that answer it\n"
        "Query: what is a composite index?"
    ]


def test_embedding_errors(api, monkeypatch):
    monkeypatch.setattr(
        embeddings.requests, "post", lambda *a, **k: FakeResponse({}, status=502)
    )
    with pytest.raises(embeddings.EmbeddingError, match="HTTP 502"):
        embeddings.embed_documents(["a"])

    def timeout(*_args, **_kwargs):
        raise requests.Timeout()

    monkeypatch.setattr(embeddings.requests, "post", timeout)
    with pytest.raises(embeddings.EmbeddingError, match="Timeout"):
        embeddings.embed_documents(["a"])

    monkeypatch.setattr(settings, "openrouter_api_key", None)
    with pytest.raises(embeddings.EmbeddingError, match="not configured"):
        embeddings.embed_documents(["a"])


@pytest.fixture
def fake_embed(monkeypatch):
    """Embed without HTTP; records the texts and uses one token per text."""
    seen = []

    def embed_documents(texts):
        seen.extend(texts)
        return [VECTOR for _ in texts], len(texts)

    monkeypatch.setattr(embeddings, "embed_documents", embed_documents)
    return seen


@pytest.fixture
def library(db_session, user):
    carded = Video(
        video_id="aaaaaaaaaaa",
        title="Indexes",
        video_metadata={"uploader": "DB Talks"},
        summary="How indexes work.",
        miscellaneous_data={
            "key_points": [
                {"text": "Order matters", "start_seconds": 1, "end_seconds": 2}
            ]
        },
    )
    bare = Video(video_id="bbbbbbbbbbb", video_metadata={"uploader": "Someone"})
    db_session.add_all([carded, bare])
    db_session.flush()
    chunk = TranscriptChunk(
        video_id=carded.video_id, idx=0, start_seconds=0, end_seconds=40, text="Hi"
    )
    written = Moment(
        user_id=user.id,
        video_id=carded.video_id,
        at_seconds=5,
        note="My note",
        ai_text="AI line",
        quote="The quote",
        source=CaptureSource.WEB,
    )
    empty = Moment(
        user_id=user.id,
        video_id=carded.video_id,
        at_seconds=50,
        note="  ",
        source=CaptureSource.WEB,
    )
    db_session.add_all([chunk, written, empty])
    db_session.flush()
    written.updated_at = datetime(2026, 1, 2, tzinfo=timezone.utc)
    db_session.flush()
    return {
        "carded": carded,
        "bare": bare,
        "chunk": chunk,
        "written": written,
        "empty": empty,
    }


def embedding(db_session, row, column="embedding"):
    db_session.expire(row)
    return getattr(row, column)


def test_embed_pending_embeds_each_kind_once(db_session, fake_embed, library):
    counts = upkeep.embed_pending(db_session, 10)

    assert (counts.chunks, counts.moments, counts.videos) == (1, 1, 1)
    assert counts.tokens == 3
    assert fake_embed == [
        "Hi",
        "My note\nAI line\nThe quote",
        "Indexes Channel: DB Talks How indexes work. Order matters",
    ]
    assert embedding(db_session, library["chunk"]) is not None
    assert embedding(db_session, library["written"]) is not None
    assert embedding(db_session, library["carded"], "card_embedding") is not None
    # Rows without text are not selected, so they are never retried.
    assert embedding(db_session, library["empty"]) is None
    assert embedding(db_session, library["bare"], "card_embedding") is None
    # Embedding is not activity.
    assert library["written"].updated_at == datetime(2026, 1, 2, tzinfo=timezone.utc)

    fake_embed.clear()
    assert upkeep.embed_pending(db_session, 10).rows == 0
    assert fake_embed == []


def test_embed_pending_respects_the_limit(db_session, fake_embed, library):
    db_session.add_all(
        TranscriptChunk(
            video_id="aaaaaaaaaaa", idx=i, start_seconds=0, end_seconds=1, text="t"
        )
        for i in range(1, 4)
    )
    db_session.flush()

    assert upkeep.embed_pending(db_session, 2).chunks == 2
    assert upkeep.embed_pending(db_session, 2).chunks == 2
    assert upkeep.embed_pending(db_session, 2).chunks == 0


def test_moment_text_changes_clear_the_embedding(db_session, library):
    moment = library["written"]
    moment.embedding = VECTOR
    db_session.flush()

    moments_service.update(db_session, moment, {"note": "My note"})
    assert embedding(db_session, moment) is not None
    moments_service.update(db_session, moment, {"note": "Edited"})
    assert embedding(db_session, moment) is None

    moment.embedding = VECTOR
    db_session.flush()
    moments_service.save_ai_text(db_session, moment, "New AI line", "model")
    assert embedding(db_session, moment) is None

    moment.embedding = VECTOR
    db_session.flush()
    moments_service._merge(db_session, moment, "More", wants_ai=False)
    db_session.flush()
    assert embedding(db_session, moment) is None

    moment.embedding = VECTOR
    db_session.flush()
    transcript = [{"text": "A different quote", "offset": 0, "duration": 10}]
    moments_service.on_transcript_stored(
        db_session, "aaaaaaaaaaa", transcript, recompute_all=True
    )
    db_session.flush()
    assert moment.quote == "A different quote"
    assert embedding(db_session, moment) is None


def test_video_card_changes_clear_the_embedding(db_session, library):
    video = library["carded"]

    def embedded():
        video.card_embedding = VECTOR
        db_session.flush()

    embedded()
    internal_service.store_summary(db_session, video.video_id, "How indexes work.")
    assert embedding(db_session, video, "card_embedding") is not None
    internal_service.store_summary(db_session, video.video_id, "New summary")
    assert embedding(db_session, video, "card_embedding") is None

    embedded()
    internal_service.store_summary(
        db_session,
        video.video_id,
        None,
        {"key_points": [{"text": "New", "start_seconds": 1, "end_seconds": 2}]},
    )
    assert embedding(db_session, video, "card_embedding") is None

    embedded()
    internal_service.store_summary(
        db_session, video.video_id, None, {"overview_model": "m"}
    )
    assert embedding(db_session, video, "card_embedding") is not None

    embedded()
    internal_service.store_metadata(
        db_session, video.video_id, {"uploader": "Renamed channel"}
    )
    assert embedding(db_session, video, "card_embedding") is None

    bare = library["bare"]
    bare.card_embedding = VECTOR
    db_session.flush()
    videos_service.get_or_create_video(db_session, bare.video_id, "A title")
    assert embedding(db_session, bare, "card_embedding") is None


def test_write_paths_do_not_call_the_embedding_api(db_session, library):
    # The autouse fixture blocks the API; these writes must not reach it.
    moments_service.update(db_session, library["written"], {"note": "Edited"})
    internal_service.store_summary(db_session, "aaaaaaaaaaa", "Changed")
    internal_service.store_transcript(
        db_session, "aaaaaaaaaaa", [{"text": "Hello", "offset": 0, "duration": 2}]
    )


class SweepSession:
    def __init__(self, db_session):
        self.db_session = db_session

    def __getattr__(self, name):
        return getattr(self.db_session, name)

    def close(self):
        pass


def test_sweep_embeds_a_bounded_batch(db_session, monkeypatch):
    monkeypatch.setattr(database, "SessionLocal", lambda: SweepSession(db_session))
    monkeypatch.setattr(settings, "openrouter_api_key", "test-openrouter-key")
    calls = []
    monkeypatch.setattr(
        sweep,
        "embed_pending",
        lambda db, limit: calls.append(limit) or upkeep.EmbedCounts(chunks=1),
    )

    sweep.sweep_once()
    assert calls == [sweep.EMBED_LIMIT]

    monkeypatch.setattr(settings, "openrouter_api_key", None)
    sweep.sweep_once()
    assert calls == [sweep.EMBED_LIMIT]


def test_sweep_survives_an_embedding_failure(db_session, monkeypatch, caplog):
    monkeypatch.setattr(database, "SessionLocal", lambda: SweepSession(db_session))
    monkeypatch.setattr(settings, "openrouter_api_key", "test-openrouter-key")

    def fail(db, limit):
        raise embeddings.EmbeddingError("Embedding API returned HTTP 502")

    monkeypatch.setattr(sweep, "embed_pending", fail)

    sweep.sweep_once()
    assert "Embedding pass failed" in caplog.text


def test_backfill_stops_past_max_tokens_and_resumes(
    db_session, fake_embed, library, monkeypatch, caplog
):
    db_session.add_all(
        TranscriptChunk(
            video_id="aaaaaaaaaaa", idx=i, start_seconds=0, end_seconds=1, text="t"
        )
        for i in range(1, 6)
    )
    db_session.flush()
    monkeypatch.setattr(database, "SessionLocal", lambda: SweepSession(db_session))
    monkeypatch.setattr(backfill, "EMBED_ROUND", 2)

    first = backfill.backfill_embeddings(max_tokens=3)
    # One round: two chunks, one moment, one video, one token each.
    assert first.tokens == 4
    assert "past --max-tokens 3" in caplog.text
    pending = db_session.query(TranscriptChunk).filter(
        TranscriptChunk.embedding.is_(None)
    )
    assert pending.count() == 4

    rest = backfill.backfill_embeddings()
    assert (rest.chunks, rest.moments, rest.videos) == (4, 0, 0)
    assert pending.count() == 0


def test_an_edit_during_the_call_keeps_the_embedding_null(
    db_session, library, monkeypatch
):
    moment = library["written"]

    def embed_documents(texts):
        # The user edits the note while the moment's request is in flight.
        if any(text.startswith("My note") for text in texts):
            db_session.execute(
                update(Moment).where(Moment.id == moment.id).values(note="Edited")
            )
        return [VECTOR for _ in texts], len(texts)

    monkeypatch.setattr(embeddings, "embed_documents", embed_documents)
    counts = upkeep.embed_pending(db_session, 10)

    assert counts.moments == 0
    assert embedding(db_session, moment) is None


def test_video_card_is_keyword_searchable(db_session, library):
    def matches(term):
        return db_session.scalars(
            select(Video.video_id).where(
                Video.card_search.op("@@")(func.plainto_tsquery("english", term))
            )
        ).all()

    for term in ("indexes", "DB Talks", "work", "order matters"):
        assert matches(term) == ["aaaaaaaaaaa"]
    assert matches("someone") == ["bbbbbbbbbbb"]
