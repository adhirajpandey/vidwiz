"""Find the sources a library question should be answered from."""

import json
import logging
from dataclasses import dataclass

from openai import OpenAI
from sqlalchemy.orm import Session

from src.ask.prompts import QUERY_TERMS_PROMPT
from src.config import settings
from src.conversations.parts import CitationPart
from src.search import service as search_service
from src.search.schemas import MomentResult
from src.shared import jev

logger = logging.getLogger(__name__)

MAX_TERMS = 12
TERMS_SCHEMA = {
    "type": "object",
    "properties": {
        "terms": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_TERMS}
    },
    "required": ["terms"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class Source:
    source_id: str
    video_id: str
    video_title: str | None
    kind: str
    start_seconds: float
    end_seconds: float
    text: str

    def citation(self) -> CitationPart:
        return CitationPart(
            type="citation",
            chunk_id=self.source_id,
            start_seconds=self.start_seconds,
            end_seconds=self.end_seconds,
            video_id=self.video_id,
        )

    def context(self) -> dict:
        return {
            "id": self.source_id,
            "kind": self.kind,
            "video": self.video_title or self.video_id,
            "start_seconds": self.start_seconds,
            "text": self.text,
        }


def expand_terms(question: str, history: list[str]) -> list[str]:
    """Search terms and synonyms for the question; empty if the model fails."""
    try:
        client = OpenAI(
            api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url
        )
        response = client.chat.completions.create(
            model=settings.ask_query_model,
            messages=[
                {
                    "role": "user",
                    "content": QUERY_TERMS_PROMPT.format(
                        history="\n".join(history[-2:]) or "(none)",
                        question=question,
                    ),
                }
            ],
            max_tokens=400,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "search_terms",
                    "strict": True,
                    "schema": TERMS_SCHEMA,
                },
            },
            extra_body={"provider": {"require_parameters": True}},
        )
        terms = json.loads(response.choices[0].message.content or "{}").get("terms", [])
    except Exception as exc:
        logger.warning("Query expansion failed", extra={"error": type(exc).__name__})
        return []
    return [term.strip() for term in terms if isinstance(term, str) and term.strip()][
        :MAX_TERMS
    ]


def _source(hit: search_service.Hit) -> Source:
    result = hit.result
    if isinstance(result, MomentResult):
        moment = result.moment
        lines = [
            f"User note: {moment.note}" if moment.note else None,
            f"AI line: {moment.ai_text}" if moment.ai_text else None,
            f"Said in the video: {moment.quote}" if moment.quote else None,
        ]
        return Source(
            source_id=f"m{moment.id}",
            video_id=result.video.video_id,
            video_title=result.video.title,
            kind="moment",
            start_seconds=result.start_seconds,
            end_seconds=max(result.start_seconds, moment.at_seconds),
            text="\n".join(line for line in lines if line),
        )
    return Source(
        source_id=f"c{result.chunk_id}",
        video_id=result.video.video_id,
        video_title=result.video.title,
        kind="transcript",
        start_seconds=result.start_seconds,
        end_seconds=result.end_seconds,
        text=hit.text,
    )


@dataclass(frozen=True)
class Retrieval:
    sources: list[Source]
    # Null when query expansion failed or relevance scoring was not used.
    query_model: str | None
    relevance_model: str | None


def retrieve(db: Session, user_id: int, question: str, history: list[str]) -> Retrieval:
    """Expand, search wide, then keep the passages Jev judges relevant.

    Without Jev, or if it fails, the best full-text matches are kept instead.
    """
    terms = expand_terms(question, history)
    query_model = settings.ask_query_model if terms else None
    query = " ".join([question, *terms])
    hits = search_service.find(
        db, user_id, query, mode="any", limit=settings.ask_candidates
    )
    if not hits:
        logger.info("Library Ask found no candidates: terms=%d", len(terms))
        return Retrieval([], query_model, None)

    sources = [_source(hit) for hit in hits]
    if not settings.jev_enabled:
        return Retrieval(sources[: settings.ask_max_sources], query_model, None)
    try:
        scores = jev.relevance(question, [source.text for source in sources])
    except jev.JevError as exc:
        logger.warning("Jev relevance failed; using full-text order: %s", exc)
        return Retrieval(sources[: settings.ask_max_sources], query_model, None)

    ranked = sorted(zip(sources, scores), key=lambda pair: pair[1], reverse=True)
    kept = [
        source for source, score in ranked if score >= settings.jev_relevance_threshold
    ][: settings.ask_max_sources]
    # One line per question, so thresholds can be tuned from real logs.
    logger.info(
        "Library Ask retrieval: model=%s terms=%d candidates=%d kept=%d "
        "threshold=%.2f top=%s",
        settings.jev_model,
        len(terms),
        len(sources),
        len(kept),
        settings.jev_relevance_threshold,
        ",".join(f"{score:.2f}" for _, score in ranked[:10]),
    )
    return Retrieval(kept, query_model, settings.jev_model)


def build_references(sources: list[Source]) -> dict[str, CitationPart]:
    return {source.source_id: source.citation() for source in sources}


def sources_json(sources: list[Source]) -> str:
    return json.dumps([source.context() for source in sources], ensure_ascii=False)
