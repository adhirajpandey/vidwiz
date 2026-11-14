"""Library Ask: answer a question with a short loop of library tool calls."""

import asyncio
import json
import logging
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from openai import OpenAI
from sqlalchemy.orm import Session

from src.ask.prompts import (
    ASK_SYSTEM_PROMPT_TEMPLATE,
    FINAL_ROUND_MESSAGE,
    LOOK_UP_MESSAGE,
)
from src.ask.sources import Source
from src.ask.tools import TOOL_SPECS, ToolContext, run_tool
from src.config import settings
from src.conversations.parts import (
    BlockPart,
    CitationPart,
    DigestPart,
    ErrorEvent,
    ModelResponse,
    PartsDecoder,
    StatsPart,
    StatusEvent,
    history_parts,
    resolve_block,
    split_block,
    stored_parts,
    text_projection,
)
from src.shared import jev

logger = logging.getLogger(__name__)

DEFAULT_TIME_ZONE = "UTC"
MAX_ROUNDS = 5
MAX_TOOL_CALLS = 6
MAX_SEARCHES = 4
MAX_TOKENS = 2500
RELEVANCE_TIMEOUT_SECONDS = 3
# Characters of a tool round's reply, without tool calls, read before it is
# treated as finished.
DRAFT_CHARS = 400
NO_RESPONSE = "No response from AI model. Please try again."
STATUS_TEXT = {
    "find_videos": "Looking through your videos",
    "search": "Searching your library",
    "moments_in": "Collecting your moments",
    "library_stats": "Counting your videos",
    "fetch": "Reading the transcript",
}
TOOL_LIMIT_ERROR = (
    "Tool call limit reached. Do not call more tools; answer from the results "
    "you already have."
)
SEARCH_LIMIT_ERROR = (
    "Search limit reached. Do not search again; answer from the results you "
    "already have."
)
NO_STRONG_MATCH_NOTE = (
    "Nothing here clearly matches the question. Unless the text plainly answers "
    "it, the answer may be that it is not in the library."
)
DISPLAY_PARTS = {"moments_in": DigestPart, "library_stats": StatsPart}

AskEvent = StatusEvent | BlockPart | DigestPart | StatsPart | ErrorEvent


@dataclass
class LoopStats:
    rounds: int = 0
    # (tool name, seconds) for every call that ran.
    tools: list[tuple[str, float]] = field(default_factory=list)
    searches: int = 0
    # A call was refused for a limit, or the last round was forced.
    limit_reached: bool = False


@dataclass
class LoopResult:
    """The outcome of one question; always the last item ``run_ask`` yields,
    except after a disconnect."""

    # Answer blocks with citations resolved, in order.
    blocks: list[BlockPart]
    # Digest and stats parts, shown and stored after the blocks.
    typed_parts: list[DigestPart | StatsPart]
    # {"model": ..., "relevance_model": ... or None}, for the saved metadata.
    models: dict
    stats: LoopStats
    # The sources the answer blocks cite, in first-cited order.
    cited: list[Source] = field(default_factory=list)
    # None on success, else why it failed: "empty_response", "invalid_output"
    # or "model_error". An ErrorEvent was yielded just before.
    failure: str | None = None

    @property
    def parts(self) -> list[BlockPart | DigestPart | StatsPart]:
        return [*self.blocks, *self.typed_parts]


def system_prompt(time_zone: str) -> str:
    today = datetime.now(ZoneInfo(time_zone))
    return ASK_SYSTEM_PROMPT_TEMPLATE.format(
        weekday=today.strftime("%A"), date=today.date().isoformat()
    )


def history_messages(history: list[dict]) -> list[dict]:
    """Earlier messages; assistant answers replay as their JSON parts.

    Earlier citations are dropped, as no source of this question backs them.
    """
    messages = []
    for message in history:
        content = message["content"]
        if message["role"] == "assistant":
            parts = stored_parts(content, message.get("metadata"))
            content = json.dumps({"parts": history_parts(parts, {})})
        messages.append({"role": message["role"], "content": content})
    return messages


def mark_relevance(question: str, result: dict, sources: list[Source]) -> bool:
    """Mark each search result strong or weak against the user's question.

    Results are never dropped. Returns whether Jev scored them; when it fails
    or is slow the result is left as it was.
    """
    if not settings.jev_enabled or not sources:
        return False
    try:
        scores = jev.relevance(
            question,
            [source.text for source in sources],
            timeout=RELEVANCE_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        logger.warning("Library Ask relevance skipped: %s", exc)
        return False
    threshold = settings.ask_relevance_threshold
    for view, score in zip(result["results"], scores):
        view["match"] = "strong" if score >= threshold else "weak"
    if all(score < threshold for score in scores):
        result["note"] = NO_STRONG_MATCH_NOTE
    return True


def looked_up(stats: LoopStats) -> bool:
    """Whether a tool that reads the library's content has run.

    find_videos alone only lists videos, so an answer after it is usually a
    note that the model will look inside them next.
    """
    return any(name != "find_videos" for name, _ in stats.tools)


class _Round:
    """Tool calls accumulated from one streamed tool round."""

    def __init__(self):
        self.calls: dict[int, dict] = {}
        self.text_chars = 0

    def add_tool_calls(self, deltas) -> None:
        for delta in deltas:
            call = self.calls.setdefault(
                delta.index, {"id": None, "name": "", "arguments": ""}
            )
            if getattr(delta, "id", None):
                call["id"] = delta.id
            function = getattr(delta, "function", None)
            if function is not None:
                call["name"] += getattr(function, "name", None) or ""
                call["arguments"] += getattr(function, "arguments", None) or ""


def run_ask(
    db: Session,
    user_id: int,
    question: str,
    history: list[dict],
    time_zone: str,
    api_key: str,
    relevance: bool = True,
) -> Iterator[AskEvent | LoopResult]:
    """Answer a library question with up to five rounds of tool calls.

    Arguments:
        db: a session; tools read the user's library through it.
        user_id: whose library and moments to read.
        question: the question as asked.
        history: earlier messages of the conversation, oldest first, without
            this question: dicts with "role" ("user" or "assistant"),
            "content" and "metadata" (the stored message metadata, or None).
        time_zone: an IANA name for local dates, such as "Asia/Kolkata".
        api_key: the OpenRouter API key.
        relevance: False skips the Jev match marks on search results.

    Yields, in order: ``StatusEvent`` when a tool starts; ``BlockPart`` for
    each answer block as it completes; ``DigestPart`` and ``StatsPart`` after
    the blocks when moments_in or library_stats ran; an ``ErrorEvent`` if the
    answer failed; and finally a ``LoopResult``. Each event is a Pydantic
    model to send as ``model_dump_json()``. Nothing is saved. Closing the
    generator early stops the loop.
    """
    stats = LoopStats()
    references: dict[str, CitationPart] = {}
    sources: dict[str, Source] = {}
    context = ToolContext(db=db, user_id=user_id, time_zone=time_zone)
    displays: dict[str, dict] = {}
    blocks: list[BlockPart] = []
    relevance_used = False
    response_stream = None
    outcome = "interrupted"

    def result(failure: str | None = None, typed_parts=()) -> LoopResult:
        return LoopResult(
            blocks=blocks,
            typed_parts=list(typed_parts),
            models={
                "model": settings.ask_model,
                "relevance_model": settings.jev_model if relevance_used else None,
            },
            stats=stats,
            cited=[
                sources[key]
                for key in dict.fromkeys(
                    key
                    for block in blocks
                    for citation in block.citations
                    for passage in citation.passages
                    for key in passage.chunk_ids
                )
            ],
            failure=failure,
        )

    messages = [
        {"role": "system", "content": system_prompt(time_zone)},
        *history_messages(history),
        {"role": "user", "content": question},
    ]
    try:
        client = OpenAI(api_key=api_key, base_url=settings.openrouter_base_url)
        answer_now = False
        while True:
            stats.rounds += 1
            forced = stats.rounds >= MAX_ROUNDS or len(stats.tools) >= MAX_TOOL_CALLS
            stats.limit_reached |= forced
            request = {
                "model": settings.ask_model,
                "messages": messages,
                "temperature": 0,
                "max_tokens": MAX_TOKENS,
                "stream": True,
                "extra_body": {
                    "reasoning": {"effort": "low"},
                    "provider": {"require_parameters": True},
                },
            }
            if forced or answer_now:
                break
            # A tool round offers the tools without the answer schema: offered
            # both, the model often answers before looking anything up, or
            # with a note that it will search next, and the schema is not
            # enforced beside tools.
            request["tools"] = TOOL_SPECS
            if not looked_up(stats):
                request["tool_choice"] = "required"
            response_stream = client.chat.completions.create(**request)
            current = _Round()
            for chunk in response_stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta is None:
                    continue
                if getattr(delta, "tool_calls", None):
                    current.add_tool_calls(delta.tool_calls)
                if delta.content:
                    current.text_chars += len(delta.content)
                    # A long reply without tool calls is a draft answer that
                    # is never shown; stop paying for it.
                    if not current.calls and current.text_chars > DRAFT_CHARS:
                        break
            response_stream.close()
            response_stream = None

            if not current.calls:
                if looked_up(stats):
                    # Done looking things up: write the answer next round.
                    answer_now = True
                elif not any(
                    message.get("content") == LOOK_UP_MESSAGE for message in messages
                ):
                    # Text before reading anything is a guess, or a note that
                    # the model will search; ask for the lookup instead.
                    messages.append({"role": "user", "content": LOOK_UP_MESSAGE})
                continue

            calls = [current.calls[index] for index in sorted(current.calls)]
            for index, call in enumerate(calls):
                call["id"] = call["id"] or f"call_{stats.rounds}_{index}"
            messages.append(
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call["id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": call["arguments"],
                            },
                        }
                        for call in calls
                    ],
                }
            )
            for call in calls:
                name = call["name"]
                if len(stats.tools) >= MAX_TOOL_CALLS:
                    stats.limit_reached = True
                    output = {"error": TOOL_LIMIT_ERROR}
                elif name == "search" and stats.searches >= MAX_SEARCHES:
                    stats.limit_reached = True
                    output = {"error": SEARCH_LIMIT_ERROR}
                else:
                    if name in STATUS_TEXT:
                        yield StatusEvent(text=STATUS_TEXT[name])
                    started = time.perf_counter()
                    ran = run_tool(name, call["arguments"], context)
                    output = ran.result
                    for source in ran.sources:
                        references[source.source_id] = source.citation()
                        sources[source.source_id] = source
                        context.seen_ids.add(source.source_id)
                    if name == "search":
                        stats.searches += 1
                        if relevance and "results" in output:
                            relevance_used |= mark_relevance(
                                question, output, ran.sources
                            )
                    if ran.display is not None and name in DISPLAY_PARTS:
                        displays[name] = ran.display
                    stats.tools.append((name, time.perf_counter() - started))
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call["id"],
                        "content": json.dumps(output, ensure_ascii=False, default=str),
                    }
                )

        # The answer round: the schema, no tools, streamed as blocks complete.
        request["messages"] = [
            *messages,
            {"role": "user", "content": FINAL_ROUND_MESSAGE},
        ]
        request["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "wiz_response",
                "strict": True,
                "schema": ModelResponse.model_json_schema(),
            },
        }
        response_stream = client.chat.completions.create(**request)
        decoder = PartsDecoder()
        finish_reason = None
        for chunk in response_stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if getattr(choice, "finish_reason", None):
                finish_reason = choice.finish_reason
            delta = choice.delta
            if getattr(delta, "refusal", None):
                raise ValueError("Model refused structured response")
            if delta and delta.content:
                for block in decoder.feed(delta.content):
                    for item in split_block(block).blocks:
                        part = resolve_block(item, references)
                        blocks.append(part)
                        yield part
        if not decoder.buffer:
            outcome = "empty_response"
            yield ErrorEvent(message=NO_RESPONSE)
            yield result("empty_response")
            return
        decoder.finish()
        if finish_reason != "stop":
            raise ValueError("Incomplete model response")
        typed_parts = [
            DISPLAY_PARTS[name].model_validate(displays[name])
            for name in DISPLAY_PARTS
            if name in displays
        ]
        if not text_projection([*blocks, *typed_parts]).strip():
            outcome = "empty_response"
            yield ErrorEvent(message=NO_RESPONSE)
            yield result("empty_response")
            return
        yield from typed_parts
        outcome = "completed"
        yield result(typed_parts=typed_parts)
    except (GeneratorExit, asyncio.CancelledError):
        raise
    except Exception as exc:
        outcome = (
            "invalid_output"
            if isinstance(exc, (ValueError, json.JSONDecodeError))
            else "model_error"
        )
        db.rollback()
        logger.exception("Library Ask failed", extra={"error_type": type(exc).__name__})
        yield ErrorEvent(message="Processing error")
        yield result(outcome)
    finally:
        if response_stream is not None and hasattr(response_stream, "close"):
            response_stream.close()
        # Values go in the message because the production log format omits `extra`.
        logger.info(
            "Library Ask loop: model=%s outcome=%s rounds=%d tools=%s searches=%d "
            "limit_reached=%s",
            settings.ask_model,
            outcome,
            stats.rounds,
            ",".join(f"{name}:{seconds:.2f}s" for name, seconds in stats.tools)
            or "none",
            stats.searches,
            stats.limit_reached,
        )


@dataclass
class AskAnswer:
    """A finished library answer, for callers without a stream."""

    # The saved-message text: blocks, then digest and stats summaries.
    text: str
    # The sources the answer cites.
    sources: list[Source]
    # Everything yielded before the result: status, blocks, digest, stats, error.
    events: list[AskEvent]
    result: LoopResult

    @property
    def parts(self) -> list[BlockPart | DigestPart | StatsPart]:
        return self.result.parts


def ask(
    db: Session,
    user_id: int,
    question: str,
    history: list[dict] | None = None,
    time_zone: str = DEFAULT_TIME_ZONE,
    *,
    api_key: str | None = None,
    relevance: bool = True,
) -> AskAnswer:
    """Run ``run_ask`` to the end and collect it; nothing is saved.

    ``api_key`` defaults to OPENROUTER_API_KEY. On failure ``result.failure``
    is set and ``events`` ends with the ErrorEvent.
    """
    events: list[AskEvent] = []
    for item in run_ask(
        db,
        user_id,
        question,
        history or [],
        time_zone,
        api_key or settings.openrouter_api_key,
        relevance,
    ):
        if isinstance(item, LoopResult):
            return AskAnswer(
                text=text_projection(item.parts),
                sources=item.cited,
                events=events,
                result=item,
            )
        events.append(item)
    raise RuntimeError("Library Ask ended without a result")
