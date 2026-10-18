"""Full-text search across a user's moments and saved videos' transcripts."""

import logging
import re
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import Float, cast, func, literal, select
from sqlalchemy.orm import Session

from src.library.models import LibraryItem
from src.moments.models import Moment
from src.moments.schemas import MomentRead
from src.search.models import TranscriptChunk
from src.search.schemas import (
    MomentResult,
    PassageResult,
    SearchResponse,
    SnippetPart,
    VideoBrief,
)
from src.videos.models import Video

logger = logging.getLogger(__name__)

# Markers that cannot appear in transcript text, split back out into parts.
HIGHLIGHT_START = "\x02"
HIGHLIGHT_STOP = "\x03"
HEADLINE_OPTIONS = (
    f"StartSel={HIGHLIGHT_START},StopSel={HIGHLIGHT_STOP},"
    "MaxWords=35,MinWords=15,MaxFragments=2,FragmentDelimiter= … "
)
# The user's own moments outrank transcript passages with the same match.
MOMENT_BOOST = 1.5
FUZZY_SNIPPET_CHARS = 220
FUZZY_THRESHOLD = 0.45
_WORD = re.compile(r"\w+", re.UNICODE)

Mode = Literal["all", "any"]


def search_terms(query: str) -> list[str]:
    return [word.lower() for word in _WORD.findall(query)][:20]


def to_tsquery_text(terms: list[str], mode: Mode) -> str:
    """Prefix-match every term; "all" requires each, "any" ranks any."""
    joiner = " & " if mode == "all" else " | "
    return joiner.join(f"{term}:*" for term in terms)


def thumbnail_url(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"


def video_brief(video_id: str, title: str | None) -> VideoBrief:
    return VideoBrief(
        video_id=video_id, title=title, thumbnail_url=thumbnail_url(video_id)
    )


def split_snippet(headline: str) -> list[SnippetPart]:
    parts: list[SnippetPart] = []
    for index, piece in enumerate(
        re.split(f"[{HIGHLIGHT_START}{HIGHLIGHT_STOP}]", headline)
    ):
        if piece:
            parts.append(SnippetPart(text=piece, highlight=index % 2 == 1))
    return parts


def _moment_text():
    return func.concat_ws(" ", Moment.note, Moment.ai_text, Moment.quote)


@dataclass(frozen=True)
class Hit:
    """A ranked moment or passage, before it is turned into a response."""

    result: MomentResult | PassageResult
    text: str


def find(
    db: Session,
    user_id: int,
    query: str,
    *,
    mode: Mode = "all",
    limit: int = 20,
    video_id: str | None = None,
    include_passages: bool = True,
) -> list[Hit]:
    """Return ranked full-text hits; used by search and by library Ask."""
    terms = search_terms(query)
    if not terms:
        return []
    tsquery = func.to_tsquery("english", to_tsquery_text(terms, mode))
    hits = _moment_hits(db, user_id, tsquery, limit, video_id)
    if include_passages:
        hits += _passage_hits(db, user_id, tsquery, limit, video_id)
    hits.sort(key=lambda hit: hit.result.score, reverse=True)
    return hits[:limit]


def _moment_hits(db, user_id, tsquery, limit, video_id) -> list[Hit]:
    score = cast(func.ts_rank_cd(Moment.search, tsquery), Float) * MOMENT_BOOST
    headline = func.ts_headline("english", _moment_text(), tsquery, HEADLINE_OPTIONS)
    query = (
        select(Moment, Video.title, score.label("score"), headline, _moment_text())
        .join(Video, Video.video_id == Moment.video_id)
        .where(Moment.user_id == user_id, Moment.search.bool_op("@@")(tsquery))
        .order_by(score.desc(), Moment.id.desc())
        .limit(limit)
    )
    if video_id:
        query = query.where(Moment.video_id == video_id)
    return [
        Hit(
            result=MomentResult(
                video=video_brief(moment.video_id, title),
                moment=MomentRead.model_validate(moment),
                start_seconds=moment.quote_start_seconds or moment.at_seconds,
                snippet=split_snippet(snippet),
                score=round(value, 6),
            ),
            text=text,
        )
        for moment, title, value, snippet, text in db.execute(query).all()
    ]


def _passage_hits(db, user_id, tsquery, limit, video_id) -> list[Hit]:
    score = cast(func.ts_rank_cd(TranscriptChunk.search, tsquery), Float)
    headline = func.ts_headline(
        "english", TranscriptChunk.text, tsquery, HEADLINE_OPTIONS
    )
    query = (
        select(TranscriptChunk, Video.title, score.label("score"), headline)
        .join(Video, Video.video_id == TranscriptChunk.video_id)
        .join(
            LibraryItem,
            (LibraryItem.video_id == TranscriptChunk.video_id)
            & (LibraryItem.user_id == user_id),
        )
        .where(TranscriptChunk.search.bool_op("@@")(tsquery))
        .order_by(score.desc(), TranscriptChunk.id)
        .limit(limit)
    )
    if video_id:
        query = query.where(TranscriptChunk.video_id == video_id)
    return [
        Hit(
            result=PassageResult(
                video=video_brief(chunk.video_id, title),
                chunk_id=chunk.id,
                start_seconds=chunk.start_seconds,
                end_seconds=chunk.end_seconds,
                snippet=split_snippet(snippet),
                score=round(value, 6),
            ),
            text=chunk.text,
        )
        for chunk, title, value, snippet in db.execute(query).all()
    ]


def _fuzzy_hits(db, user_id, query_text, limit, video_id) -> list[Hit]:
    """Trigram word similarity, for queries with typos and no exact match."""
    # The default 0.6 threshold misses single-letter typos in short words.
    db.execute(
        sql_text(f"SET LOCAL pg_trgm.word_similarity_threshold = {FUZZY_THRESHOLD}")
    )
    # Matches the moments_text_trgm_idx expression, so the index applies.
    words = (
        func.coalesce(Moment.note, "") + " " + func.coalesce(Moment.ai_text, "")
    ).self_group()
    moment_score = func.word_similarity(literal(query_text), words)
    moments = (
        select(Moment, Video.title, moment_score)
        .join(Video, Video.video_id == Moment.video_id)
        .where(Moment.user_id == user_id, literal(query_text).bool_op("<%")(words))
        .order_by(moment_score.desc(), Moment.id.desc())
        .limit(limit)
    )
    chunk_score = func.word_similarity(literal(query_text), TranscriptChunk.text)
    chunks = (
        select(TranscriptChunk, Video.title, chunk_score)
        .join(Video, Video.video_id == TranscriptChunk.video_id)
        .join(
            LibraryItem,
            (LibraryItem.video_id == TranscriptChunk.video_id)
            & (LibraryItem.user_id == user_id),
        )
        .where(literal(query_text).bool_op("<%")(TranscriptChunk.text))
        .order_by(chunk_score.desc(), TranscriptChunk.id)
        .limit(limit)
    )
    if video_id:
        moments = moments.where(Moment.video_id == video_id)
        chunks = chunks.where(TranscriptChunk.video_id == video_id)

    hits = [
        Hit(
            result=MomentResult(
                video=video_brief(moment.video_id, title),
                moment=MomentRead.model_validate(moment),
                start_seconds=moment.quote_start_seconds or moment.at_seconds,
                snippet=[
                    SnippetPart(
                        text=_clip(moment.ai_text or moment.note or moment.quote or ""),
                        highlight=False,
                    )
                ],
                score=round(float(value) * MOMENT_BOOST, 6),
            ),
            text=" ".join(filter(None, [moment.note, moment.ai_text, moment.quote])),
        )
        for moment, title, value in db.execute(moments).all()
    ]
    hits += [
        Hit(
            result=PassageResult(
                video=video_brief(chunk.video_id, title),
                chunk_id=chunk.id,
                start_seconds=chunk.start_seconds,
                end_seconds=chunk.end_seconds,
                snippet=[SnippetPart(text=_clip(chunk.text), highlight=False)],
                score=round(float(value), 6),
            ),
            text=chunk.text,
        )
        for chunk, title, value in db.execute(chunks).all()
    ]
    hits.sort(key=lambda hit: hit.result.score, reverse=True)
    return hits[:limit]


def _clip(text: str) -> str:
    text = " ".join(text.split())
    if len(text) <= FUZZY_SNIPPET_CHARS:
        return text
    return text[:FUZZY_SNIPPET_CHARS].rsplit(" ", 1)[0] + " …"


def search(
    db: Session,
    user_id: int,
    query: str,
    page: int,
    per_page: int,
    video_id: str | None = None,
) -> SearchResponse:
    window = page * per_page + 1
    logger.debug(
        "Searching", extra={"user_id": user_id, "page": page, "video_id": video_id}
    )
    hits = find(db, user_id, query, limit=window, video_id=video_id)
    match = "exact"
    if not hits:
        hits = _fuzzy_hits(db, user_id, " ".join(search_terms(query)), window, video_id)
        match = "fuzzy" if hits else "none"
    start = (page - 1) * per_page
    return SearchResponse(
        query=query,
        match=match,
        results=[hit.result for hit in hits[start : start + per_page]],
        page=page,
        per_page=per_page,
        has_more=len(hits) > start + per_page,
    )
