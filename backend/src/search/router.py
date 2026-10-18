from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user_id
from src.config import settings
from src.database import get_db
from src.exceptions import BadRequestError
from src.search import service as search_service
from src.search.schemas import SearchResponse
from src.shared.ratelimit import limiter
from src.videos.utils import normalize_youtube_video_id

router = APIRouter(prefix="/v2", tags=["Search"])


@router.get(
    "/search",
    response_model=SearchResponse,
    description=(
        "Search the user's moments and the transcripts of saved videos. Every "
        "term must match (as a word prefix, with stemming). With no full-text "
        "match, results fall back to typo-tolerant similarity (match=fuzzy). "
        "Optional video_id limits the search to one video."
    ),
)
@limiter.limit(settings.rate_limit_videos)
def search(
    request: Request,
    response: Response,
    q: str = Query(min_length=2, max_length=200),
    page: int = Query(default=1, ge=1, le=20),
    per_page: int = Query(default=20, ge=1, le=50),
    video_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> SearchResponse:
    if not search_service.search_terms(q):
        raise BadRequestError("Enter a word to search for")
    if video_id:
        try:
            video_id = normalize_youtube_video_id(video_id)
        except ValueError as exc:
            raise BadRequestError(str(exc)) from exc
    return search_service.search(db, user_id, q, page, per_page, video_id)
