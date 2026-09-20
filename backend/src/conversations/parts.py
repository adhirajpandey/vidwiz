"""Wiz's product parts, transcript references, and incremental JSON framing."""

import hashlib
import json
import math
import logging
from typing import Annotated, Literal

from markdown_it import MarkdownIt
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TextPart(StrictModel):
    type: Literal["text"]
    text: str


class ChunkReference(StrictModel):
    type: Literal["citation"]
    chunk_id: str = Field(min_length=1)


class CitationPart(ChunkReference):
    start_seconds: float = Field(ge=0, allow_inf_nan=False)
    end_seconds: float = Field(ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def ordered_times(self):
        if self.end_seconds < self.start_seconds:
            raise ValueError("Citation ends before it starts")
        return self


ModelPart = Annotated[TextPart | ChunkReference, Field(discriminator="type")]


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
model_part_adapter = TypeAdapter(ModelPart)
message_parts_adapter = TypeAdapter(list[MessagePart])


class ModelResponse(StrictModel):
    # Plain union generates portable anyOf JSON Schema without an OpenAPI discriminator.
    parts: list[TextPart | ChunkReference]


class ModelResponseV2(StrictModel):
    parts: list[ModelBlock]


def resolve_block(block: ModelBlock, references: dict[str, CitationPart]) -> BlockPart:
    """Validate structural targets, then group evidence only within each target."""
    logger = logging.getLogger(__name__)
    tokens = MarkdownIt("commonmark").enable("table").parse(block.text)
    roots = [
        t for t in tokens if t.level == 0 and t.nesting != -1 and t.type != "inline"
    ]
    list_items = sum(t.type == "list_item_open" and t.level == 1 for t in tokens)
    is_list = len(roots) == 1 and roots[0].type in {
        "bullet_list_open",
        "ordered_list_open",
    }
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
    parts: list[MessagePart], references: dict[str, CitationPart], version: int
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
            if version == 2:
                result.append(
                    ModelBlock(
                        type="block",
                        text=part.text,
                        references=[s for s in sources if s.chunk_ids],
                    ).model_dump()
                )
            else:
                result.append(TextPart(type="text", text=part.text).model_dump())
                result.extend(
                    {"type": "citation", "chunk_id": key}
                    for s in sources
                    for key in s.chunk_ids
                )
        elif isinstance(part, TextPart):
            result.append(
                ModelBlock(type="block", text=part.text, references=[]).model_dump()
                if version == 2
                else part.model_dump()
            )
        elif version == 1 and part.chunk_id in references:
            result.append({"type": "citation", "chunk_id": part.chunk_id})
        # Legacy citations have no explicit block association. Do not invent one in v2.
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

    def __init__(self, version: int = 1):
        self.response_model = ModelResponseV2 if version == 2 else ModelResponse
        self.part_adapter = (
            TypeAdapter(ModelBlock) if version == 2 else model_part_adapter
        )
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

    def finish(self) -> ModelResponse | ModelResponseV2:
        response = self.response_model.model_validate(
            json.loads(
                self.buffer,
                object_pairs_hook=_unique_object,
            )
        )
        if response.parts != self.parts:
            raise ValueError("Invalid streamed parts")
        return response
