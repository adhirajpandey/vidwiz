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


@dataclass
class EmbedCounts:
    chunks: int = 0
    moments: int = 0
    videos: int = 0
    tokens: int = 0

    @property
    def rows(self) -> int:
        return self.chunks + self.moments + self.videos

    def add(self, other: "EmbedCounts") -> None:
        self.chunks += other.chunks
        self.moments += other.moments
        self.videos += other.videos
        self.tokens += other.tokens


def moment_text(note: str | None, ai_text: str | None, quote: str | None) -> str:
    return "\n".join(
        part.strip() for part in (note, ai_text, quote) if part and part.strip()
    )


def video_card_text(
    title: str | None,
    metadata: dict | None,
    summary: str | None,
    miscellaneous_data: dict | None,
) -> str:
    """Title, channel, summary and key points; empty without title, summary or
    key points, since a channel alone says nothing about the video."""
    points = (miscellaneous_data or {}).get("key_points")
    point_texts = [
        point.get("text")
        for point in (points if isinstance(points, list) else [])
        if isinstance(point, dict) and isinstance(point.get("text"), str)
    ]
    content = [part for part in (title, summary, *point_texts) if part and part.strip()]
    if not content:
        return ""
    channel = (metadata or {}).get("uploader")
    parts = [title, f"Channel: {channel}" if channel else None, summary, *point_texts]
    return " ".join(part.strip() for part in parts if part and part.strip())


def _has_text(*columns):
    return func.length(func.trim(func.concat_ws("", *columns))) > 0


def _embed_rows(
    db: Session, rows: Sequence, texts: list[str], write
) -> tuple[int, int]:
    """Embed in API-sized batches, committing each, so a stopped run keeps its
    work. Returns rows written and tokens used."""
    written = tokens = 0
    for start in range(0, len(rows), embeddings.BATCH_SIZE):
        batch = rows[start : start + embeddings.BATCH_SIZE]
        vectors, used = embeddings.embed_documents(
            texts[start : start + embeddings.BATCH_SIZE]
        )
        tokens += used
        for row, vector in zip(batch, vectors):
            written += db.execute(write(row, vector)).rowcount
        db.commit()
    return written, tokens


def _embed_chunks(db: Session, limit: int) -> tuple[int, int]:
    rows = db.execute(
        select(TranscriptChunk.id, TranscriptChunk.text)
        .where(TranscriptChunk.embedding.is_(None))
        .order_by(TranscriptChunk.id.desc())
        .limit(limit)
    ).all()
    # Passages are replaced, never edited, so a missing id is the only race.
    return _embed_rows(
        db,
        rows,
        [row.text for row in rows],
        lambda row, vector: (
            update(TranscriptChunk)
            .where(TranscriptChunk.id == row.id, TranscriptChunk.embedding.is_(None))
            .values(embedding=vector)
        ),
    )


def _embed_moments(db: Session, limit: int) -> tuple[int, int]:
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
    return _embed_rows(
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
    )


def _embed_videos(db: Session, limit: int) -> tuple[int, int]:
    metadata_text = cast(Video.video_metadata, Text)
    misc_text = cast(Video.miscellaneous_data, Text)
    rows = db.execute(
        select(
            Video.id,
            Video.title,
            Video.summary,
            Video.video_metadata,
            Video.miscellaneous_data,
            metadata_text.label("metadata_text"),
            misc_text.label("misc_text"),
        )
        .where(
            Video.card_embedding.is_(None),
            or_(
                _has_text(Video.title, Video.summary),
                func.jsonb_path_exists(
                    cast(Video.miscellaneous_data, JSONB), "$.key_points[*].text"
                ),
            ),
        )
        .order_by(Video.id.desc())
        .limit(limit)
    ).all()
    texts = [
        video_card_text(
            row.title, row.video_metadata, row.summary, row.miscellaneous_data
        )
        for row in rows
    ]
    kept = [(row, text) for row, text in zip(rows, texts) if text]
    return _embed_rows(
        db,
        [row for row, _ in kept],
        [text for _, text in kept],
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
    )


def embed_pending(db: Session, limit: int) -> EmbedCounts:
    """Embed up to `limit` rows of each kind that have no embedding yet."""
    counts = EmbedCounts()
    counts.chunks, tokens = _embed_chunks(db, limit)
    counts.tokens += tokens
    counts.moments, tokens = _embed_moments(db, limit)
    counts.tokens += tokens
    counts.videos, tokens = _embed_videos(db, limit)
    counts.tokens += tokens
    return counts
