"""Wiz's product parts, transcript references, and incremental JSON framing."""

import hashlib
import json
import math
import logging
import re
from enum import Enum
from typing import Annotated, Literal, NamedTuple

from markdown_it import MarkdownIt
from markdown_it.token import Token
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TextPart(StrictModel):
    type: Literal["text"]
    text: str


class CitationPart(StrictModel):
    """A transcript segment reference; stored standalone only by v1 messages."""

    type: Literal["citation"]
    chunk_id: str = Field(min_length=1)
    start_seconds: float = Field(ge=0, allow_inf_nan=False)
    end_seconds: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def ordered_times(self):
        if self.end_seconds < self.start_seconds:
            raise ValueError("Citation ends before it starts")
        return self


class BlockReference(StrictModel):
    # Zero-based top-level list item; null means the complete block.
    list_item_index: int | None
    chunk_ids: list[str]


class ModelBlock(StrictModel):
    type: Literal["block"]
    text: str
    references: list[BlockReference]


class Passage(StrictModel):
    chunk_ids: list[str]
    start_seconds: float = Field(ge=0, allow_inf_nan=False)
    end_seconds: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def ordered_times(self):
        if self.end_seconds < self.start_seconds:
            raise ValueError("Passage ends before it starts")
        return self


class BlockCitation(StrictModel):
    list_item_index: int | None
    passages: list[Passage]


class BlockPart(StrictModel):
    type: Literal["block"]
    text: str
    citations: list[BlockCitation]


MessagePart = Annotated[
    TextPart | CitationPart | BlockPart, Field(discriminator="type")
]
message_parts_adapter = TypeAdapter(list[MessagePart])


class ModelResponse(StrictModel):
    parts: list[ModelBlock]


class DropReason(str, Enum):
    AMBIGUOUS_LIST = "ambiguous_list"
    INDEX_OUT_OF_RANGE = "index_out_of_range"
    NO_CONTENT_PART = "no_content_part"
    LINK_DEFINITIONS = "link_definitions"


class DroppedReference(StrictModel):
    reason: DropReason
    chunk_ids: list[str]


class SplitResult(StrictModel):
    # Every block holds exactly one top-level Markdown element, unless the source
    # was returned unchanged. Every reference that was not carried over is in dropped.
    blocks: list[ModelBlock]
    dropped: list[DroppedReference]


_markdown = MarkdownIt("commonmark").enable("table")
_LIST_OPEN = {"bullet_list_open", "ordered_list_open"}


class _ParsedMarkdown(NamedTuple):
    roots: list[Token]
    list_items: int
    has_link_definitions: bool


def _parse_markdown(text: str) -> _ParsedMarkdown:
    env: dict = {}
    tokens = _markdown.parse(text, env)
    return _ParsedMarkdown(
        roots=[
            t for t in tokens if t.level == 0 and t.nesting != -1 and t.type != "inline"
        ],
        list_items=sum(t.type == "list_item_open" and t.level == 1 for t in tokens),
        has_link_definitions=bool(env.get("references")),
    )


def _reference_target(
    index: int | None, roots: list[Token], list_items: int
) -> int | DropReason:
    """Return the root index that receives a reference, or why it cannot."""
    if index is None:
        return next(
            (i for i in reversed(range(len(roots))) if roots[i].type != "heading_open"),
            DropReason.NO_CONTENT_PART,
        )
    lists = [i for i, root in enumerate(roots) if root.type in _LIST_OPEN]
    if len(lists) > 1:
        return DropReason.AMBIGUOUS_LIST
    if not lists or not 0 <= index < list_items:
        return DropReason.INDEX_OUT_OF_RANGE
    return lists[0]


def split_block(block: ModelBlock) -> SplitResult:
    """Split a multi-element block into one block per top-level element.

    Models sometimes return a whole answer as one block. Each element keeps its
    exact source lines and references are re-targeted onto the element they
    describe, so evidence still lands beside the claim it supports.
    """
    parsed = _parse_markdown(block.text)
    roots = parsed.roots
    if len(roots) <= 1:
        return SplitResult(blocks=[block], dropped=[])
    # Markdown-it drops link reference definitions from the tokens, so splitting
    # could separate a definition from the elements that use it. The block stays
    # whole and multi-element, which resolve_block and the frontend cannot attach
    # references to, so report them as dropped.
    if parsed.has_link_definitions:
        return SplitResult(
            blocks=[block],
            dropped=[
                DroppedReference(
                    reason=DropReason.LINK_DEFINITIONS, chunk_ids=source.chunk_ids
                )
                for source in block.references
            ],
        )
    lines = re.split(r"\r\n|\r|\n", block.text)
    references: list[list[BlockReference]] = [[] for _ in roots]
    dropped: list[DroppedReference] = []
    for source in block.references:
        target = _reference_target(source.list_item_index, roots, parsed.list_items)
        if isinstance(target, DropReason):
            dropped.append(DroppedReference(reason=target, chunk_ids=source.chunk_ids))
        else:
            references[target].append(source)
    return SplitResult(
        blocks=[
            ModelBlock(
                type="block",
                text="\n".join(lines[root.map[0] : root.map[1]]).rstrip("\n"),
                references=references[i],
            )
            for i, root in enumerate(roots)
        ],
        dropped=dropped,
    )


def resolve_block(block: ModelBlock, references: dict[str, CitationPart]) -> BlockPart:
    """Validate structural targets, then group evidence only within each target."""
    logger = logging.getLogger(__name__)
    roots, list_items, _ = _parse_markdown(block.text)
    is_list = len(roots) == 1 and roots[0].type in _LIST_OPEN
    targets: dict[int | None, set[str]] = {}
    for source in block.references:
        index = source.list_item_index
        if len(roots) != 1 or (
            index is not None and (not is_list or not 0 <= index < list_items)
        ):
            logger.warning("Omitting invalid Wiz block reference target")
            continue
        ids = targets.setdefault(index, set())
        for chunk_id in source.chunk_ids:
            if chunk_id in references:
                ids.add(chunk_id)
            else:
                logger.warning(
                    "Omitting invalid Wiz block source", extra={"chunk_id": chunk_id}
                )
    citations = []
    for index, ids in targets.items():
        passages: list[Passage] = []
        for source in sorted(
            (references[key] for key in ids),
            key=lambda r: (r.start_seconds, r.end_seconds, r.chunk_id),
        ):
            previous = passages[-1] if passages else None
            if (
                previous is not None
                and source.start_seconds <= previous.end_seconds + 5
                and max(previous.end_seconds, source.end_seconds)
                - previous.start_seconds
                <= 60
            ):
                previous.end_seconds = max(previous.end_seconds, source.end_seconds)
                previous.chunk_ids.append(source.chunk_id)
            else:
                passages.append(
                    Passage(
                        chunk_ids=[source.chunk_id],
                        start_seconds=source.start_seconds,
                        end_seconds=source.end_seconds,
                    )
                )
        if passages:
            citations.append(BlockCitation(list_item_index=index, passages=passages))
    return BlockPart(type="block", text=block.text, citations=citations)


def history_parts(
    parts: list[MessagePart], references: dict[str, CitationPart]
) -> list[dict]:
    """Replay evidence IDs without trusting stored times after transcript replacement."""
    result = []
    for part in parts:
        if isinstance(part, BlockPart):
            sources = [
                BlockReference(
                    list_item_index=c.list_item_index,
                    chunk_ids=[
                        key
                        for p in c.passages
                        for key in p.chunk_ids
                        if key in references
                    ],
                )
                for c in part.citations
            ]
            result.append(
                ModelBlock(
                    type="block",
                    text=part.text,
                    references=[s for s in sources if s.chunk_ids],
                ).model_dump()
            )
        elif isinstance(part, TextPart):
            result.append(
                ModelBlock(type="block", text=part.text, references=[]).model_dump()
            )
        # Legacy citations have no explicit block association. Do not invent one.
    return result


class DoneEvent(StrictModel):
    type: Literal["done"] = "done"
    message_id: int


class ErrorEvent(StrictModel):
    type: Literal["error"] = "error"
    message: str


def stored_parts(content: str, metadata: dict | None) -> list[MessagePart]:
    if metadata and metadata.get("parts_version") in (1, 2):
        return message_parts_adapter.validate_python(metadata["parts"])
    return [TextPart(type="text", text=content)]


def text_projection(parts: list[MessagePart]) -> str:
    return "\n\n".join(
        part.text for part in parts if isinstance(part, (TextPart, BlockPart))
    )


def _seconds(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= 0 else None


def transcript_context(transcript: list) -> tuple[list[dict], dict[str, CitationPart]]:
    revision = hashlib.sha256(
        json.dumps(
            transcript,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode()
    ).hexdigest()[:24]
    context = []
    references = {}
    for index, segment in enumerate(transcript):
        if not isinstance(segment, dict) or not isinstance(segment.get("text"), str):
            continue
        start = _seconds(segment.get("offset"))
        duration = _seconds(segment.get("duration"))
        end = None
        if start is not None:
            if "duration" in segment:
                end = _seconds(start + duration) if duration is not None else None
            else:
                end = next(
                    (
                        offset
                        for later in transcript[index + 1 :]
                        if isinstance(later, dict)
                        and (offset := _seconds(later.get("offset"))) is not None
                        and offset > start
                    ),
                    start,
                )
        if start is None or end is None:
            context.append({"text": segment["text"], "citable": False})
            continue
        chunk_id = f"chunk_{revision}_{index}"
        citation = CitationPart(
            type="citation", chunk_id=chunk_id, start_seconds=start, end_seconds=end
        )
        references[chunk_id] = citation
        context.append(
            {
                "id": chunk_id,
                "text": segment["text"],
                "start_seconds": start,
                "end_seconds": end,
            }
        )
    return context, references


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


class PartsDecoder:
    """Frame complete objects without interpreting Markdown or incomplete strings.

    Final envelope validation is mandatory even after parts have been emitted.
    The scan cursor makes framing linear in the size of the provider response.
    """

    part_adapter = TypeAdapter(ModelBlock)

    def __init__(self):
        self.buffer = ""
        self.stack = []
        self.in_string = False
        self.escaped = False
        self.part_start = None
        self.started = False
        self.parts = []

    def feed(self, delta: str):
        offset = len(self.buffer)
        self.buffer += delta
        if len(self.buffer) > 1_000_000:
            raise ValueError("Structured response too large")
        for index in range(offset, len(self.buffer)):
            char = self.buffer[index]
            if self.in_string:
                if self.escaped:
                    self.escaped = False
                elif char == "\\":
                    self.escaped = True
                elif char == '"':
                    self.in_string = False
                continue
            if char == '"':
                self.in_string = True
            elif char in "{[":
                if char == "{" and self.stack == ["{", "["]:
                    if not self.started:
                        prefix = json.loads(
                            self.buffer[:index] + "null]}",
                            object_pairs_hook=_unique_object,
                        )
                        if prefix != {"parts": [None]}:
                            raise ValueError("Invalid parts envelope")
                        self.started = True
                    self.part_start = index
                self.stack.append(char)
            elif char in "}]":
                if not self.stack or self.stack.pop() != ("{" if char == "}" else "["):
                    raise ValueError("Invalid JSON nesting")
                if (
                    char == "}"
                    and self.stack == ["{", "["]
                    and self.part_start is not None
                ):
                    value = json.loads(
                        self.buffer[self.part_start : index + 1],
                        object_pairs_hook=_unique_object,
                    )
                    part = self.part_adapter.validate_python(value)
                    self.parts.append(part)
                    self.part_start = None
                    yield part

    def finish(self) -> ModelResponse:
        response = ModelResponse.model_validate(
            json.loads(
                self.buffer,
                object_pairs_hook=_unique_object,
            )
        )
        if response.parts != self.parts:
            raise ValueError("Invalid streamed parts")
        return response
