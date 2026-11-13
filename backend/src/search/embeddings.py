"""Keep embeddings of transcript passages, moments and video cards up to date.

A null embedding means "not embedded yet". New passages start null, and the
write paths clear a moment's or video's embedding when its text changes. The
sweep and the backfill call `embed_pending`; nothing else calls the API.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import Text, cast, func, or_, select, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from src.moments.models import Moment
from src.search.models import TranscriptChunk
from src.shared import embeddings
from src.videos.models import Video

logger = logging.getLogger(__name__)

# Text that is only these characters counts as empty, in Python and SQL alike,
# so rows the SQL selects always produce text.
WHITESPACE = " \t\n\r\f\v"
KEY_POINT_TEXTS = '$.key_points[*].text ? (@.type() == "string")'
NONBLANK_KEY_POINT = (
    r'$.key_points[*].text ? (@.type() == "string" && @ like_regex "[^ \t\n\r\f\v]")'
)


@dataclass
class EmbedCounts:
    chunks: int = 0
    moments: int = 0
    videos: int = 0
    tokens: int = 0

    @property
    def rows(self) -> int:
        return self.chunks + self.moments + self.videos


def moment_text(note: str | None, ai_text: str | None, quote: str | None) -> str:
    return _join("\n", note, ai_text, quote)


def video_card_text(
    title: str | None,
    channel: str | None,
    summary: str | None,
    key_points: list[str],
) -> str:
    """Title, channel, summary and key points; empty without title, summary or
    key points, since a channel alone says nothing about the video."""
    if not _join("", title, summary, *key_points):
        return ""
    return _join(
        " ", title, f"Channel: {channel}" if channel else None, summary, *key_points
    )


def _join(separator: str, *parts: str | None) -> str:
    stripped = (part.strip(WHITESPACE) for part in parts if isinstance(part, str))
    return separator.join(part for part in stripped if part)


def _has_text(*columns):
    return func.btrim(func.concat_ws("", *columns), WHITESPACE) != ""


def _embed_rows(
    db: Session,
    rows: Sequence,
    texts: list[str],
    write,
    kind: str,
    counts: "EmbedCounts",
    max_tokens: int | None,
) -> None:
    """Embed in API-sized batches, committing each and adding it to `counts`,
    so a stopped or failed run keeps its work and its count. No request is
    sent once `counts.tokens` is past `max_tokens`."""
    for start in range(0, len(rows), embeddings.BATCH_SIZE):
        if max_tokens is not None and counts.tokens > max_tokens:
            return
        batch = rows[start : start + embeddings.BATCH_SIZE]
        vectors, used = embeddings.embed_documents(
            texts[start : start + embeddings.BATCH_SIZE]
        )
        written = sum(
            db.execute(write(row, vector)).rowcount
            for row, vector in zip(batch, vectors)
        )
        db.commit()
        counts.tokens += used
        setattr(counts, kind, getattr(counts, kind) + written)


def _embed_chunks(db: Session, limit: int, counts, max_tokens) -> None:
    rows = db.execute(
        select(TranscriptChunk.id, TranscriptChunk.text)
        .where(TranscriptChunk.embedding.is_(None), _has_text(TranscriptChunk.text))
        .order_by(TranscriptChunk.id.desc())
        .limit(limit)
    ).all()
    # Passages are replaced, never edited, so a missing id is the only race.
    _embed_rows(
        db,
        rows,
        [row.text.strip(WHITESPACE) for row in rows],
        lambda row, vector: (
            update(TranscriptChunk)
            .where(TranscriptChunk.id == row.id, TranscriptChunk.embedding.is_(None))
            .values(embedding=vector)
        ),
        "chunks",
        counts,
        max_tokens,
    )


def _embed_moments(db: Session, limit: int, counts, max_tokens) -> None:
    # Moments without any text are never selected, so they are not retried;
    # once text is added they qualify.
    rows = db.execute(
        select(Moment.id, Moment.note, Moment.ai_text, Moment.quote)
        .where(
            Moment.embedding.is_(None),
            _has_text(Moment.note, Moment.ai_text, Moment.quote),
        )
        .order_by(Moment.id.desc())
        .limit(limit)
    ).all()
    # The text must still match, so an edit during the call is not overwritten
    # with a stale vector.
    _embed_rows(
        db,
        rows,
        [moment_text(row.note, row.ai_text, row.quote) for row in rows],
        lambda row, vector: (
            update(Moment)
            .where(
                Moment.id == row.id,
                Moment.embedding.is_(None),
                Moment.note.is_not_distinct_from(row.note),
                Moment.ai_text.is_not_distinct_from(row.ai_text),
                Moment.quote.is_not_distinct_from(row.quote),
            )
            # Embedding is upkeep, not activity: updated_at keeps its value.
            .values(embedding=vector, updated_at=Moment.updated_at)
        ),
        "moments",
        counts,
        max_tokens,
    )


def _embed_videos(db: Session, limit: int, counts, max_tokens) -> None:
    metadata_text = cast(Video.video_metadata, Text)
    misc_text = cast(Video.miscellaneous_data, Text)
    misc = cast(Video.miscellaneous_data, JSONB)
    # The filter and the card text read the same key point strings with the
    # same blank rule, so every selected video has card text.
    rows = db.execute(
        select(
            Video.id,
            Video.title,
            Video.summary,
            Video.video_metadata["uploader"].as_string().label("channel"),
            func.jsonb_path_query_array(misc, KEY_POINT_TEXTS).label("key_points"),
            metadata_text.label("metadata_text"),
            misc_text.label("misc_text"),
        )
        .where(
            Video.card_embedding.is_(None),
            or_(
                _has_text(Video.title, Video.summary),
                func.jsonb_path_exists(misc, NONBLANK_KEY_POINT),
            ),
        )
        .order_by(Video.id.desc())
        .limit(limit)
    ).all()
    _embed_rows(
        db,
        rows,
        [
            video_card_text(row.title, row.channel, row.summary, row.key_points)
            for row in rows
        ],
        lambda row, vector: (
            update(Video)
            .where(
                Video.id == row.id,
                Video.card_embedding.is_(None),
                Video.title.is_not_distinct_from(row.title),
                Video.summary.is_not_distinct_from(row.summary),
                metadata_text.is_not_distinct_from(row.metadata_text),
                misc_text.is_not_distinct_from(row.misc_text),
            )
            # Embedding is upkeep, not activity: updated_at keeps its value.
            .values(card_embedding=vector, updated_at=Video.updated_at)
        ),
        "videos",
        counts,
        max_tokens,
    )


def embed_pending(
    db: Session,
    limit: int,
    counts: EmbedCounts | None = None,
    max_tokens: int | None = None,
) -> EmbedCounts:
    """Embed up to `limit` rows of each kind that have no embedding yet.

    Each committed batch is added to `counts` as it lands, so a caller that
    passes its own counts still has them when a later batch raises. No request
    is sent once `counts.tokens` is past `max_tokens`.
    """
    counts = counts if counts is not None else EmbedCounts()
    _embed_chunks(db, limit, counts, max_tokens)
    _embed_moments(db, limit, counts, max_tokens)
    _embed_videos(db, limit, counts, max_tokens)
    return counts
