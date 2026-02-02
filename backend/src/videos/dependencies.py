from fastapi import Depends, Query
from sqlalchemy.orm import Session

from src.database import get_db
from src.exceptions import BadRequestError, NotFoundError
from src.videos import constants as video_constants
from src.auth.dependencies import get_current_user_id, get_viewer_context
from src.videos import service as videos_service
from src.videos.schemas import VideoIdPath, VideoListParams


def get_video_list_params(
    q: str = Query(default="", alias="q"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=10, ge=1, le=50),
    sort: str = Query(default="created_at_desc"),
) -> VideoListParams:
    if sort not in video_constants.VIDEO_SORT_KEYS:
        raise BadRequestError("Invalid sort parameter")

    return VideoListParams(q=q, page=page, per_page=per_page, sort=sort)


def get_user_video_or_404(
    path: VideoIdPath = Depends(),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    _ = user_id
    video = videos_service.get_video_by_id(db, path.video_id)
    if not video:
        raise NotFoundError("Video not found")
    return video


def get_user_video_id_or_404(
    video=Depends(get_user_video_or_404),
) -> str:
    return video.video_id


def get_stream_video_or_404(
    path: VideoIdPath = Depends(),
    db: Session = Depends(get_db),
    viewer=Depends(get_viewer_context),
):
    if viewer.user_id:
        video = videos_service.get_video_for_user(db, viewer.user_id, path.video_id)
    else:
        video = videos_service.get_video_by_id(db, path.video_id)
    if not video:
        raise NotFoundError("Video not found")
    return video


def get_stream_video_id_or_404(
    video=Depends(get_stream_video_or_404),
) -> str:
    return video.video_id
