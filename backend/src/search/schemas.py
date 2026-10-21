from typing import Annotated, Literal

from pydantic import Field

from src.models import ApiModel
from src.moments.schemas import MomentRead


class VideoBrief(ApiModel):
    video_id: str
    title: str | None
    thumbnail_url: str


class SnippetPart(ApiModel):
    text: str
    highlight: bool


class MomentResult(ApiModel):
    kind: Literal["moment"] = "moment"
    video: VideoBrief
    moment: MomentRead
    start_seconds: int
    snippet: list[SnippetPart]
    score: float


class PassageResult(ApiModel):
    kind: Literal["passage"] = "passage"
    video: VideoBrief
    chunk_id: int
    start_seconds: int
    end_seconds: int
    snippet: list[SnippetPart]
    score: float


SearchResult = Annotated[MomentResult | PassageResult, Field(discriminator="kind")]


class SearchResponse(ApiModel):
    query: str
    # exact: full-text matches; fuzzy: no full-text match, so trigram
    # similarity tolerated typos; none: nothing matched either way.
    match: Literal["exact", "fuzzy", "none"]
    results: list[SearchResult]
    page: int
    per_page: int
    has_more: bool
