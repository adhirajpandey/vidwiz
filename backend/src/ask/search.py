"""Hybrid search for Library Ask: keyword and embedding rankings, fused.

Passages come from videos in the user's library and moments are the user's
own. Without an embedding (no API key, or the call failed) the keyword
rankings are used alone.
"""

import logging
import re
from dataclasses import dataclass

from sqlalchemy import Float, Select, cast, func, select
from sqlalchemy.orm import Session

from src.ask.sources import Source, moment_source
from src.library.models import LibraryItem
from src.moments.models import Moment
from src.search.models import TranscriptChunk
from src.search.service import to_tsquery_text
from src.shared import embeddings
from src.videos.models import Video

logger = logging.getLogger(__name__)

STOP_WORDS = frozenset(
    "a an the of in on at to for is are was were do does did i my me what which "
    "who how why about and or with from have has there one where that this it "
    "they he she".split()
)
MAX_TERMS = 20
RANKING_LIMIT = 40
MOMENT_WEIGHT = 1.5
RRF_K = 60
MAX_PER_VIDEO = 2
MAX_VIDEOS = 3
SUMMARY_CHARS = 200
_WORD = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class VideoCard:
    video_id: str
    title: str | None
    channel: str | None
    summary: str | None

    def view(self) -> dict:
        return {
            "video_id": self.video_id,
            "title": self.title,
            "channel": self.channel,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class SearchResults:
    sources: list[Source]
    videos: list[VideoCard]


def query_terms(query: str) -> list[str]:
    """The query's words without stop words, at most MAX_TERMS."""
    words = (word.lower() for word in _WORD.findall(query))
    return [word for word in words if word not in STOP_WORDS][:MAX_TERMS]


def channel_column():
    return Video.video_metadata["uploader"].as_string()


def library_join(query: Select, video_column, user_id: int) -> Select:
    return query.join(
        LibraryItem,
        (LibraryItem.video_id == video_column) & (LibraryItem.user_id == user_id),
    )


def passage_source(chunk: TranscriptChunk, title, channel) -> Source:
    return Source(
        source_id=f"c{chunk.id}",
        video_id=chunk.video_id,
        video_title=title,
        kind="transcript",
        start_seconds=chunk.start_seconds,
        end_seconds=chunk.end_seconds,
        text=chunk.text,
        channel=channel,
    )


def _passages(db, user_id, video_ids, score, where, order) -> list[tuple]:
    query = library_join(
        select(TranscriptChunk, Video.title, channel_column(), score).join(
            Video, Video.video_id == TranscriptChunk.video_id
        ),
        TranscriptChunk.video_id,
        user_id,
    ).where(where)
    if video_ids is not None:
        query = query.where(TranscriptChunk.video_id.in_(video_ids))
    rows = db.execute(
        query.order_by(order, TranscriptChunk.id).limit(RANKING_LIMIT)
    ).all()
    return [
        (passage_source(chunk, title, channel), value)
        for chunk, title, channel, value in rows
    ]


def _moments(db, user_id, video_ids, time_zone, score, where, order) -> list[tuple]:
    query = library_join(
        select(Moment, Video.title, channel_column(), score).join(
            Video, Video.video_id == Moment.video_id
        ),
        Moment.video_id,
        user_id,
    ).where(Moment.user_id == user_id, where)
    if video_ids is not None:
        query = query.where(Moment.video_id.in_(video_ids))
    rows = db.execute(
        query.order_by(order, Moment.id.desc()).limit(RANKING_LIMIT)
    ).all()
    return [
        (moment_source(moment, title, time_zone, channel), value)
        for moment, title, channel, value in rows
    ]


def keyword_ranking(db, user_id, terms, video_ids, time_zone) -> list[Source]:
    if not terms:
        return []
    tsquery = func.to_tsquery("english", to_tsquery_text(terms, "any"))
    passage_score = cast(func.ts_rank_cd(TranscriptChunk.search, tsquery), Float)
    moment_score = cast(func.ts_rank_cd(Moment.search, tsquery), Float) * MOMENT_WEIGHT
    rows = _passages(
        db,
        user_id,
        video_ids,
        passage_score,
        TranscriptChunk.search.bool_op("@@")(tsquery),
        passage_score.desc(),
    ) + _moments(
        db,
        user_id,
        video_ids,
        time_zone,
        moment_score,
        Moment.search.bool_op("@@")(tsquery),
        moment_score.desc(),
    )
    rows.sort(key=lambda row: row[1], reverse=True)
    return [source for source, _ in rows]


def embedding_ranking(db, user_id, vector, video_ids, time_zone) -> list[Source]:
    passage_distance = TranscriptChunk.embedding.cosine_distance(vector)
    moment_distance = Moment.embedding.cosine_distance(vector)
    rows = _passages(
        db,
        user_id,
        video_ids,
        passage_distance,
        TranscriptChunk.embedding.is_not(None),
        passage_distance,
    ) + _moments(
        db,
        user_id,
        video_ids,
        time_zone,
        moment_distance,
        Moment.embedding.is_not(None),
        moment_distance,
    )
    rows.sort(key=lambda row: row[1])
    return [source for source, _ in rows[:RANKING_LIMIT]]


def fuse(*rankings: list, key=lambda item: item) -> list:
    """Reciprocal rank fusion; ties keep first-seen order."""
    scores: dict = {}
    items: dict = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            item_key = key(item)
            scores[item_key] = scores.get(item_key, 0.0) + 1 / (RRF_K + rank + 1)
            items.setdefault(item_key, item)
    ordered = sorted(scores, key=lambda item_key: scores[item_key], reverse=True)
    return [items[item_key] for item_key in ordered]


def cap_per_video(sources: list[Source], cap: int = MAX_PER_VIDEO) -> list[Source]:
    counts: dict[str, int] = {}
    kept = []
    for source in sources:
        counts[source.video_id] = counts.get(source.video_id, 0) + 1
        if counts[source.video_id] <= cap:
            kept.append(source)
    return kept


def card_ranking(db, user_id, terms, vector) -> list[VideoCard]:
    base = library_join(
        select(Video.video_id, Video.title, channel_column(), Video.summary),
        Video.video_id,
        user_id,
    )
    rankings = []
    if terms:
        tsquery = func.to_tsquery("english", to_tsquery_text(terms, "any"))
        score = func.ts_rank_cd(Video.card_search, tsquery)
        rankings.append(
            db.execute(
                base.where(Video.card_search.bool_op("@@")(tsquery))
                .order_by(score.desc(), Video.id)
                .limit(RANKING_LIMIT)
            ).all()
        )
    if vector is not None:
        distance = Video.card_embedding.cosine_distance(vector)
        rankings.append(
            db.execute(
                base.where(Video.card_embedding.is_not(None))
                .order_by(distance, Video.id)
                .limit(RANKING_LIMIT)
            ).all()
        )
    rows = fuse(*rankings, key=lambda row: row[0])[:MAX_VIDEOS]
    return [
        VideoCard(
            video_id=video_id,
            title=title,
            channel=channel,
            summary=summary[:SUMMARY_CHARS] if summary else None,
        )
        for video_id, title, channel, summary in rows
    ]


def query_embedding(query: str) -> list[float] | None:
    """The query's vector, or None when embedding is unavailable."""
    try:
        vector, _ = embeddings.embed_query(query)
    except Exception as exc:
        logger.warning(
            "Ask search is using keywords only", extra={"error": type(exc).__name__}
        )
        return None
    return vector


def search(
    db: Session,
    user_id: int,
    query: str,
    video_ids: list[str] | None = None,
    limit: int = 8,
    time_zone: str = "UTC",
) -> SearchResults:
    """Up to `limit` passages and moments, and up to three matching videos.

    `video_ids` limits passages and moments (not videos) to those videos, still
    inside the user's library. `time_zone` sets moments' local capture dates.
    """
    if not query.strip():
        return SearchResults(sources=[], videos=[])
    terms = query_terms(query)
    vector = query_embedding(query)
    keyword = keyword_ranking(db, user_id, terms, video_ids, time_zone)
    rankings = [keyword]
    if vector is not None:
        rankings.append(embedding_ranking(db, user_id, vector, video_ids, time_zone))
    fused = fuse(*rankings, key=lambda source: source.source_id)
    return SearchResults(
        sources=cap_per_video(fused)[:limit],
        videos=card_ranking(db, user_id, terms, vector),
    )
