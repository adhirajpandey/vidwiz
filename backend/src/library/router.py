from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user_id
from src.config import settings
from src.database import get_db
from src.exceptions import NotFoundError
from src.internal.scheduling import prepare_video
from src.library import service as library_service
from src.library.schemas import LibraryParams, LibraryResponse, LibrarySort
from src.models import MessageResponse
from src.shared.ratelimit import limiter
from src.videos.dependencies import get_video_id_path
from src.videos.schemas import VideoIdPath

router = APIRouter(prefix="/v2/library", tags=["Library"])


@router.get("", response_model=LibraryResponse, description="List saved videos.")
@limiter.limit(settings.rate_limit_videos)
def list_library(
    request: Request,
    response: Response,
    q: str = Query(default="", max_length=200),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=50),
    sort: LibrarySort = Query(default="activity_desc"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> LibraryResponse:
    params = LibraryParams(q=q, page=page, per_page=per_page, sort=sort)
    return library_service.list_library(db, user_id, params)


@router.put(
    "/{video_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    description="Save a video by ID or URL. Fetches its transcript and metadata.",
)
def save_video(
    path: VideoIdPath = Depends(get_video_id_path),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> MessageResponse:
    prepare_video(db, path.video_id)
    library_service.save_video(db, user_id, path.video_id)
    db.commit()
    return MessageResponse(message="Saved")


@router.delete(
    "/{video_id}",
    response_model=MessageResponse,
    description="Remove a video from the library. Its moments are kept.",
)
def remove_video(
    path: VideoIdPath = Depends(get_video_id_path),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> MessageResponse:
    if not library_service.remove_video(db, user_id, path.video_id):
        raise NotFoundError("Video is not in your library")
    return MessageResponse(message="Removed")
