"""Tools a Library Ask answer model can call over the user's library.

Each tool takes validated arguments and a ToolContext and returns a
JSON-serialisable result for the model plus the sources it showed, so citations
can be resolved later. Dates are local dates in the context's time zone.
"""

import difflib
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.ask import search as ask_search
from src.ask.search import channel_column, library_join, passage_source
from src.ask.sources import Source, moment_source
from src.library.models import LibraryItem
from src.moments.models import Moment
from src.search.models import TranscriptChunk
from src.videos.models import TranscriptStatus, Video

logger = logging.getLogger(__name__)

MAX_VIDEOS = 40
MAX_GROUPS = 15
MOMENTS_PER_VIDEO = 6
MOMENT_TEXT_CHARS = 160
SUMMARY_CHARS = 200
CLOSE_NAMES = 5
CLOSE_CUTOFF = 0.5
SOURCE_ID = r"^[cm][0-9]+$"


@dataclass
class ToolContext:
    db: Session
    user_id: int
    time_zone: str
    # Source ids returned by earlier tool calls in this request; fetch reads
    # only these.
    seen_ids: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class ToolResult:
    result: dict
    sources: list[Source] = field(default_factory=list)


def error(message: str) -> ToolResult:
    return ToolResult({"error": message})


def source_view(source: Source) -> dict:
    """A source as the model sees it."""
    view = {**source.context(), "video_id": source.video_id, "channel": source.channel}
    if source.kind == "transcript":
        view["end_seconds"] = source.end_seconds
    return view


# ---- arguments ----


class Arguments(BaseModel):
    # Models sometimes add keys of their own; they are ignored.
    model_config = ConfigDict(extra="ignore")


class VideoFilter(Arguments):
    channel: str | None = None
    title_contains: str | None = None
    saved_from: date | None = None
    saved_to: date | None = None


class FindVideosArgs(VideoFilter):
    pass


class SearchArgs(Arguments):
    query: str = Field(min_length=1)
    video_ids: list[str] | None = None


class MomentsInArgs(Arguments):
    since: date
    until: date

    @model_validator(mode="after")
    def ordered(self):
        if self.since > self.until:
            raise ValueError("since must not be after until")
        return self


class LibraryStatsArgs(VideoFilter):
    group_by: Literal["channel", "month", "none"] | None = None


class FetchArgs(Arguments):
    source_id: str = Field(pattern=SOURCE_ID)


# ---- video filters ----


def normal(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def channel_names(db: Session, user_id: int) -> list[str]:
    query = library_join(
        select(channel_column()).distinct(), Video.video_id, user_id
    ).where(channel_column().is_not(None))
    return sorted(db.execute(query).scalars())


def match_channels(names: list[str], channel: str) -> tuple[list[str], list[str]]:
    """Names that loosely match the channel, and close names when none do.

    Names compare lowercased with only letters and digits; one must contain the
    other. An empty normalised name, on either side, matches nothing.
    """
    wanted = normal(channel)
    if not wanted:
        return [], []
    normals = {name: normal(name) for name in names}
    matched = [
        name
        for name, value in normals.items()
        if value and (wanted in value or value in wanted)
    ]
    if matched:
        return matched, []
    close = difflib.get_close_matches(
        wanted,
        [value for value in normals.values() if value],
        CLOSE_NAMES,
        CLOSE_CUTOFF,
    )
    return [], [name for name, value in normals.items() if value in close]


def local_start(day: date, time_zone: str) -> datetime:
    return datetime.combine(day, time.min, tzinfo=ZoneInfo(time_zone))


def filtered_videos(context: ToolContext, args: VideoFilter, *columns):
    """A query over the user's library videos matching the filter, or a note
    when the channel matches nothing."""
    query = library_join(
        select(*columns).select_from(Video), Video.video_id, context.user_id
    )
    channel = (args.channel or "").strip()
    if channel:
        matched, close = match_channels(
            channel_names(context.db, context.user_id), channel
        )
        if not matched:
            return None, (
                f"No channel matches '{channel}'. Closest channel names: {close}. "
                "The person may also appear in titles; try title_contains."
            )
        query = query.where(channel_column().in_(matched))
    title = (args.title_contains or "").strip()
    if title:
        query = query.where(Video.title.icontains(title, autoescape=True))
    if args.saved_from:
        query = query.where(
            LibraryItem.added_at >= local_start(args.saved_from, context.time_zone)
        )
    if args.saved_to:
        query = query.where(
            LibraryItem.added_at
            < local_start(args.saved_to + timedelta(days=1), context.time_zone)
        )
    return query, None


# ---- tools ----


def find_videos(args: FindVideosArgs, context: ToolContext) -> ToolResult:
    query, note = filtered_videos(
        context,
        args,
        Video.video_id,
        Video.title,
        channel_column(),
        LibraryItem.added_at,
        Video.transcript_status,
        func.left(Video.summary, SUMMARY_CHARS),
    )
    if note:
        return ToolResult({"note": note})
    total = context.db.execute(
        select(func.count()).select_from(query.subquery())
    ).scalar_one()
    rows = context.db.execute(
        query.order_by(LibraryItem.added_at.desc(), Video.id.desc()).limit(MAX_VIDEOS)
    ).all()
    zone = ZoneInfo(context.time_zone)
    return ToolResult(
        {
            "total": total,
            "videos": [
                {
                    "video_id": video_id,
                    "title": title,
                    "channel": channel,
                    "saved": added_at.astimezone(zone).date().isoformat(),
                    "has_transcript": status == TranscriptStatus.READY,
                    "summary": summary,
                }
                for video_id, title, channel, added_at, status, summary in rows
            ],
        }
    )


def search(args: SearchArgs, context: ToolContext) -> ToolResult:
    found = ask_search.search(
        context.db,
        context.user_id,
        args.query,
        video_ids=args.video_ids or None,
        time_zone=context.time_zone,
    )
    return ToolResult(
        {
            "results": [source_view(source) for source in found.sources],
            "videos": [video.view() for video in found.videos],
        },
        found.sources,
    )


def moments_in(args: MomentsInArgs, context: ToolContext) -> ToolResult:
    rows = context.db.execute(
        library_join(
            select(Moment, Video.title, channel_column()).join(
                Video, Video.video_id == Moment.video_id
            ),
            Moment.video_id,
            context.user_id,
        )
        .where(
            Moment.user_id == context.user_id,
            Moment.created_at >= local_start(args.since, context.time_zone),
            Moment.created_at
            < local_start(args.until + timedelta(days=1), context.time_zone),
        )
        .order_by(Moment.created_at, Moment.id)
    ).all()
    videos: dict[str, dict] = {}
    # Only the moments listed in the result are its sources.
    shown: list[Source] = []
    for moment, title, channel in rows:
        entry = videos.setdefault(
            moment.video_id,
            {
                "title": title,
                "video_id": moment.video_id,
                "moment_count": 0,
                "moments": [],
            },
        )
        entry["moment_count"] += 1
        if len(entry["moments"]) < MOMENTS_PER_VIDEO:
            text = moment.note or moment.ai_text or moment.quote or ""
            entry["moments"].append(
                {
                    "id": f"m{moment.id}",
                    "at_seconds": moment.at_seconds,
                    "text": text[:MOMENT_TEXT_CHARS],
                }
            )
            shown.append(moment_source(moment, title, context.time_zone, channel))
    return ToolResult(
        {
            "total_moments": len(rows),
            "video_count": len(videos),
            "videos": list(videos.values()),
        },
        shown,
    )


def library_stats(args: LibraryStatsArgs, context: ToolContext) -> ToolResult:
    if args.group_by == "channel":
        group = channel_column()
    elif args.group_by == "month":
        group = func.to_char(
            func.timezone(context.time_zone, LibraryItem.added_at), "YYYY-MM"
        )
    else:
        group = None
    count = func.count()
    columns = (count,) if group is None else (group, count)
    query, note = filtered_videos(context, args, *columns)
    if note:
        return ToolResult({"note": note})
    if group is None:
        return ToolResult({"video_count": context.db.execute(query).scalar_one()})
    rows = context.db.execute(
        query.group_by(group).order_by(count.desc(), group).limit(MAX_GROUPS)
    ).all()
    return ToolResult(
        {"groups": [{"name": name, "videos": videos} for name, videos in rows]}
    )


def _window(context: ToolContext, video_id: str, idx: int) -> list[Source]:
    rows = context.db.execute(
        select(TranscriptChunk, Video.title, channel_column())
        .join(Video, Video.video_id == TranscriptChunk.video_id)
        .where(
            TranscriptChunk.video_id == video_id,
            TranscriptChunk.idx.between(idx - 1, idx + 1),
        )
        .order_by(TranscriptChunk.idx)
    ).all()
    return [passage_source(chunk, title, channel) for chunk, title, channel in rows]


def fetch(args: FetchArgs, context: ToolContext) -> ToolResult:
    source_id = args.source_id
    if source_id not in context.seen_ids:
        return error("Use a source ID already returned by a tool.")
    db, ident = context.db, int(source_id[1:])
    moment = None
    if source_id[0] == "c":
        anchor = db.execute(
            library_join(
                select(TranscriptChunk.video_id, TranscriptChunk.idx),
                TranscriptChunk.video_id,
                context.user_id,
            ).where(TranscriptChunk.id == ident)
        ).first()
        if anchor is None:
            return error("Source no longer available.")
        video_id, idx = anchor
    else:
        row = db.execute(
            library_join(select(Moment), Moment.video_id, context.user_id).where(
                Moment.id == ident, Moment.user_id == context.user_id
            )
        ).scalar_one_or_none()
        if row is None:
            return error("Source no longer available.")
        video_id = row.video_id
        moment = {
            "id": source_id,
            "at_seconds": row.at_seconds,
            "user_note": row.note,
            "ai_line": row.ai_text,
            "quote": row.quote,
        }
        idx = db.execute(
            select(TranscriptChunk.idx)
            .where(TranscriptChunk.video_id == video_id)
            .order_by(
                func.abs(TranscriptChunk.start_seconds - row.at_seconds),
                TranscriptChunk.idx,
            )
            .limit(1)
        ).scalar_one_or_none()
        if idx is None:
            return ToolResult(
                {"moment": moment, "passages": [], "status": "transcript_unavailable"}
            )
    passages = _window(context, video_id, idx)
    result = {"passages": [source_view(source) for source in passages], "status": "ok"}
    if moment:
        result = {"moment": moment, **result}
    return ToolResult(result, passages)


# ---- definitions ----


@dataclass(frozen=True)
class Tool:
    run: Callable[[BaseModel, ToolContext], ToolResult]
    arguments: type[Arguments]
    spec: dict


FILTERS = {
    "channel": {
        "type": "string",
        "description": "Channel or creator name, matched loosely",
    },
    "title_contains": {
        "type": "string",
        "description": "Text the video title must contain",
    },
    "saved_from": {
        "type": "string",
        "description": "YYYY-MM-DD, first local date saved",
    },
    "saved_to": {
        "type": "string",
        "description": "YYYY-MM-DD, last local date saved",
    },
}


def _spec(name: str, description: str, properties: dict, required: list[str], **extra):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                **extra,
            },
        },
    }


TOOLS: dict[str, Tool] = {
    "find_videos": Tool(
        find_videos,
        FindVideosArgs,
        _spec(
            "find_videos",
            "List saved videos by channel, title text or the date they were "
            "saved. Returns ids for scoping a search.",
            FILTERS,
            [],
        ),
    ),
    "search": Tool(
        search,
        SearchArgs,
        _spec(
            "search",
            "Search what is said in saved videos and the user's captured moments "
            "and notes. Pass video_ids to search only inside those videos.",
            {
                "query": {"type": "string"},
                "video_ids": {"type": "array", "items": {"type": "string"}},
            },
            ["query"],
        ),
    ),
    "moments_in": Tool(
        moments_in,
        MomentsInArgs,
        _spec(
            "moments_in",
            "All moments the user captured between two local dates, grouped by "
            "video with true counts.",
            {"since": {"type": "string"}, "until": {"type": "string"}},
            ["since", "until"],
        ),
    ),
    "library_stats": Tool(
        library_stats,
        LibraryStatsArgs,
        _spec(
            "library_stats",
            "Count saved videos, optionally filtered, optionally grouped by "
            "channel or month.",
            {
                **FILTERS,
                "group_by": {"type": "string", "enum": ["channel", "month", "none"]},
            },
            [],
        ),
    ),
    "fetch": Tool(
        fetch,
        FetchArgs,
        _spec(
            "fetch",
            "Read surrounding transcript context for a source ID returned by "
            "search or moments_in. Returns that passage and up to one passage "
            "before and after it, with original source IDs and timestamps. Use "
            "when a snippet is incomplete or needs explanation. For a moment, "
            "returns its original note and the transcript window around its "
            "timestamp. Cannot discover a new video.",
            {"source_id": {"type": "string", "pattern": SOURCE_ID}},
            ["source_id"],
            additionalProperties=False,
        ),
    ),
}
TOOL_SPECS = [tool.spec for tool in TOOLS.values()]


def run_tool(
    name: str, raw_arguments: str | dict | None, context: ToolContext
) -> ToolResult:
    """Run a tool by name with the model's raw arguments; never raises.

    Arguments may be a JSON object string, as models send them, or a dict;
    missing, null or empty arguments mean {}. The ids of the sources a call
    returns are added to `context.seen_ids`, so they can be fetched.
    """
    tool = TOOLS.get(name)
    if tool is None:
        return error(f"Unknown tool '{name}'.")
    try:
        if isinstance(raw_arguments, str) and raw_arguments.strip():
            raw_arguments = json.loads(raw_arguments)
        if raw_arguments is None or (
            isinstance(raw_arguments, str) and not raw_arguments.strip()
        ):
            raw_arguments = {}
        if not isinstance(raw_arguments, dict):
            raise ValueError("arguments must be a JSON object")
        arguments = tool.arguments.model_validate(raw_arguments)
    except (ValueError, ValidationError) as exc:
        return error(f"Invalid arguments for {name}: {_reason(exc)}")
    try:
        result = tool.run(arguments, context)
    except SQLAlchemyError as exc:
        context.db.rollback()
        logger.warning(
            "Ask tool failed", extra={"tool": name, "error": type(exc).__name__}
        )
        return error(f"{name} failed.")
    except Exception as exc:
        logger.warning(
            "Ask tool failed", extra={"tool": name, "error": type(exc).__name__}
        )
        return error(f"{name} failed.")
    context.seen_ids.update(source.source_id for source in result.sources)
    return result


def _reason(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return "; ".join(
            f"{'.'.join(str(part) for part in item['loc']) or 'arguments'}: {item['msg']}"
            for item in exc.errors()
        )
    return "arguments must be a JSON object"
