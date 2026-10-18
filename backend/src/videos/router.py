from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import StreamingResponse

from src.config import settings
from src.videos import service as videos_service
from src.videos.dependencies import (
    get_user_video_or_404,
    get_stream_video_id_or_404,
)

from src.videos.schemas import VideoRead
from src.shared.ratelimit import limiter


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
@limiter.limit(settings.rate_limit_videos)
def get_video(
    request: Request,
    response: Response,
    video=Depends(get_user_video_or_404),
) -> VideoRead:
    return VideoRead.model_validate(video)


@router.get("/{video_id}/stream", status_code=status.HTTP_200_OK)
@limiter.limit(settings.rate_limit_videos)
async def stream_video(
    request: Request,
    response: Response,
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
