"""Find the sources a library question should be answered from."""

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.ask.prompts import QUERY_PLAN_PROMPT
from src.config import settings
from src.conversations.parts import CitationPart
from src.moments.models import Moment
from src.moments.schemas import MomentRead
from src.search import service as search_service
from src.search.schemas import MomentResult
from src.shared import jev
from src.videos.models import Video

logger = logging.getLogger(__name__)

MAX_TERMS = 12
DEFAULT_TIME_ZONE = "UTC"
PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "terms": {"type": "array", "items": {"type": "string"}, "maxItems": MAX_TERMS},
        "since": {"type": ["string", "null"]},
        "until": {"type": ["string", "null"]},
        "topic": {"type": "boolean"},
    },
    "required": ["terms", "since", "until", "topic"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class TimeRange:
    """Local capture dates, both inclusive, in the user's time zone."""

    since: date
    until: date
    time_zone: str

    def bounds(self) -> tuple[datetime, datetime]:
        """Start and exclusive end as aware datetimes."""
        zone = ZoneInfo(self.time_zone)
        start = datetime.combine(self.since, time.min, tzinfo=zone)
        end = datetime.combine(self.until + timedelta(days=1), time.min, tzinfo=zone)
        return start, end

    def as_metadata(self) -> dict:
        return {
            "since": self.since.isoformat(),
            "until": self.until.isoformat(),
            "time_zone": self.time_zone,
        }


@dataclass(frozen=True)
class QueryPlan:
    terms: list[str]
    time_range: TimeRange | None
    has_topic: bool
    # False when the model call failed and only the question itself is searched.
    planned: bool


@dataclass(frozen=True)
class Source:
    source_id: str
    video_id: str
    video_title: str | None
    kind: str
    start_seconds: float
    end_seconds: float
    text: str
    # The user's local capture date; moments only.
    captured: date | None = None

    def citation(self) -> CitationPart:
        return CitationPart(
            type="citation",
            chunk_id=self.source_id,
            start_seconds=self.start_seconds,
            end_seconds=self.end_seconds,
            video_id=self.video_id,
        )

    def context(self) -> dict:
        context = {
            "id": self.source_id,
            "kind": self.kind,
            "video": self.video_title or self.video_id,
            "start_seconds": self.start_seconds,
            "text": self.text,
        }
        if self.captured:
            context["captured"] = self.captured.isoformat()
        return context


def local_today(time_zone: str) -> date:
    return datetime.now(ZoneInfo(time_zone)).date()


def parse_time_range(
    since: object, until: object, today: date, time_zone: str
) -> TimeRange | None:
    """A checked range from the model's dates, or None when there is none.

    A missing end means up to today; a range entirely in the future, reversed, or
    unparseable is dropped so the question falls back to a normal search.
    """
    if not isinstance(since, str):
        return None
    try:
        start = date.fromisoformat(since)
        end = date.fromisoformat(until) if isinstance(until, str) else today
    except ValueError:
        logger.warning("Ignoring unparseable Ask time range")
        return None
    end = min(end, today)
    if start > end:
        logger.warning("Ignoring empty or future Ask time range")
        return None
    return TimeRange(since=start, until=end, time_zone=time_zone)


def request_plan(question: str, history: list[str], today: date) -> dict:
    """Ask the query model for a search plan; raises when the call fails."""
    client = OpenAI(
        api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url
    )
    response = client.chat.completions.create(
        model=settings.ask_query_model,
        messages=[
            {
                "role": "user",
                "content": QUERY_PLAN_PROMPT.format(
                    history="\n".join(history[-2:]) or "(none)",
                    question=question,
                    today=today.isoformat(),
                    today_weekday=today.strftime("%A"),
                ),
            }
        ],
        max_tokens=400,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "search_plan",
                "strict": True,
                "schema": PLAN_SCHEMA,
            },
        },
        extra_body={"provider": {"require_parameters": True}},
    )
    return json.loads(response.choices[0].message.content or "{}")


def plan_query(question: str, history: list[str], time_zone: str) -> QueryPlan:
    """Search terms and an optional time range; a plain search if planning fails."""
    today = local_today(time_zone)
    unplanned = QueryPlan(terms=[], time_range=None, has_topic=True, planned=False)
    try:
        plan = request_plan(question, history, today)
    except Exception as exc:
        logger.warning("Query planning failed", extra={"error": type(exc).__name__})
        return unplanned
    terms = plan.get("terms") if isinstance(plan, dict) else None
    if not isinstance(terms, list):
        logger.warning("Query planning returned an unexpected shape")
        return unplanned
    return QueryPlan(
        terms=[
            term.strip() for term in terms if isinstance(term, str) and term.strip()
        ][:MAX_TERMS],
        time_range=parse_time_range(
            plan.get("since"), plan.get("until"), today, time_zone
        ),
        has_topic=plan.get("topic") is not False,
        planned=True,
    )


def _moment_source(
    moment: MomentRead | Moment, video_title: str | None, time_zone: str
) -> Source:
    lines = [
        f"User note: {moment.note}" if moment.note else None,
        f"AI line: {moment.ai_text}" if moment.ai_text else None,
        f"Said in the video: {moment.quote}" if moment.quote else None,
    ]
    return Source(
        source_id=f"m{moment.id}",
        video_id=moment.video_id,
        video_title=video_title,
        kind="moment",
        start_seconds=moment.at_seconds,
        end_seconds=moment.at_seconds,
        text="\n".join(line for line in lines if line),
        captured=moment.created_at.astimezone(ZoneInfo(time_zone)).date(),
    )


def _source(hit: search_service.Hit, time_zone: str) -> Source:
    result = hit.result
    if isinstance(result, MomentResult):
        return _moment_source(result.moment, result.video.title, time_zone)
    return Source(
        source_id=f"c{result.chunk_id}",
        video_id=result.video.video_id,
        video_title=result.video.title,
        kind="transcript",
        start_seconds=result.start_seconds,
        end_seconds=result.end_seconds,
        text=hit.text,
    )


def captured_in(db: Session, user_id: int, time_range: TimeRange) -> list[Source]:
    """The newest moments captured in the range, for questions about a period."""
    start, end = time_range.bounds()
    rows = db.execute(
        select(Moment, Video.title)
        .join(Video, Video.video_id == Moment.video_id)
        .where(
            Moment.user_id == user_id,
            Moment.created_at >= start,
            Moment.created_at < end,
        )
        .order_by(Moment.created_at.desc(), Moment.id.desc())
        .limit(settings.ask_time_range_max_sources)
    ).all()
    return [
        _moment_source(moment, title, time_range.time_zone) for moment, title in rows
    ]


@dataclass(frozen=True)
class Retrieval:
    sources: list[Source]
    # Null when query planning failed or relevance scoring was not used.
    query_model: str | None
    relevance_model: str | None
    # Set when the question was limited to moments captured in a period.
    time_range: TimeRange | None = None


def retrieve(
    db: Session,
    user_id: int,
    question: str,
    history: list[str],
    time_zone: str = DEFAULT_TIME_ZONE,
) -> Retrieval:
    """Plan the question, then gather its sources.

    A question only about a period gets the newest moments captured then. Any
    other question searches wide, limited to that period's moments when it has
    one, and keeps the candidates Jev judges relevant. Without Jev, or if it
    fails, the best full-text matches are kept instead.
    """
    plan = plan_query(question, history, time_zone)
    query_model = settings.ask_query_model if plan.planned else None
    time_range = plan.time_range
    if time_range and not plan.has_topic:
        sources = captured_in(db, user_id, time_range)
        logger.info(
            "Library Ask time range: since=%s until=%s moments=%d",
            time_range.since,
            time_range.until,
            len(sources),
        )
        return Retrieval(sources, query_model, None, time_range)

    query = " ".join([question, *plan.terms])
    hits = search_service.find(
        db,
        user_id,
        query,
        mode="any",
        limit=settings.ask_candidates,
        # Transcript passages have no capture time, so a period keeps moments only.
        include_passages=time_range is None,
        captured_between=time_range.bounds() if time_range else None,
    )
    if not hits:
        logger.info("Library Ask found no candidates: terms=%d", len(plan.terms))
        return Retrieval([], query_model, None, time_range)

    sources = [_source(hit, time_zone) for hit in hits]
    if not settings.jev_enabled:
        return Retrieval(
            sources[: settings.ask_max_sources], query_model, None, time_range
        )
    try:
        scores = jev.relevance(question, [source.text for source in sources])
    except jev.JevError as exc:
        logger.warning("Jev relevance failed; using full-text order: %s", exc)
        return Retrieval(
            sources[: settings.ask_max_sources], query_model, None, time_range
        )

    ranked = sorted(zip(sources, scores), key=lambda pair: pair[1], reverse=True)
    kept = [
        source for source, score in ranked if score >= settings.jev_relevance_threshold
    ][: settings.ask_max_sources]
    # One line per question, so thresholds can be tuned from real logs.
    logger.info(
        "Library Ask retrieval: model=%s terms=%d candidates=%d kept=%d "
        "threshold=%.2f top=%s",
        settings.jev_model,
        len(plan.terms),
        len(sources),
        len(kept),
        settings.jev_relevance_threshold,
        ",".join(f"{score:.2f}" for _, score in ranked[:10]),
    )
    return Retrieval(kept, query_model, settings.jev_model, time_range)


def build_references(sources: list[Source]) -> dict[str, CitationPart]:
    return {source.source_id: source.citation() for source in sources}


def sources_json(sources: list[Source]) -> str:
    return json.dumps([source.context() for source in sources], ensure_ascii=False)
