from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user_id
from src.database import get_db
from src.videos import service as videos_service
from src.videos.dependencies import (
    get_user_video_or_404,
    get_video_list_params,
    get_stream_video_id_or_404,
)

from src.videos.schemas import VideoListParams, VideoListResponse, VideoRead


router = APIRouter(prefix="/v2/videos", tags=["Videos"])


@router.get(
    "/{video_id}",
    response_model=VideoRead,
    status_code=status.HTTP_200_OK,
    description=(
        "Fetch current video state (metadata, transcript availability, summary) "
        "for the authenticated user."
    ),
)
def get_video(
    video=Depends(get_user_video_or_404),
) -> VideoRead:
    return VideoRead.model_validate(video)


@router.get(
    "",
    response_model=VideoListResponse,
    status_code=status.HTTP_200_OK,
    description=(
        "Search/filter videos (q, pagination, sort). "
        "Sort options: created_at_desc, created_at_asc, title_asc, title_desc."
    ),
)
def list_videos(
    params: VideoListParams = Depends(get_video_list_params),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> VideoListResponse:
    return videos_service.list_videos_for_user(db, user_id, params)


@router.get("/{video_id}/stream", status_code=status.HTTP_200_OK)
async def stream_video(
    video_id: str = Depends(get_stream_video_id_or_404),
):
    """
    SSE stream of video state; emits snapshot/update/done when metadata + transcript
    + summary are all ready (timeout 60s).
    """
    return StreamingResponse(
        videos_service.stream_video_events(video_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
