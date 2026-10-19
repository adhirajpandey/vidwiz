from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import StreamingResponse

from sqlalchemy.orm import Session

from src.config import settings
from src.database import get_db
from src.videos import service as videos_service
from src.videos.dependencies import (
    get_stream_video_id_or_404,
    get_stream_video_or_404,
)

from src.auth.dependencies import get_viewer_context
from src.auth.schemas import ViewerContext
from src.credits import service as credits_service
from src.videos.schemas import AskStatus, TranscriptRead, VideoRead
from src.shared.ratelimit import limiter


router = APIRouter(prefix="/v2/videos", tags=["Videos"])


@router.get(
    "/{video_id}",
    response_model=VideoRead,
    status_code=status.HTTP_200_OK,
    description=(
        "Fetch current video state (metadata, transcript availability, summary, "
        "overview). JWT or guest session."
    ),
)
@limiter.limit(settings.rate_limit_videos)
def get_video(
    request: Request,
    response: Response,
    video=Depends(get_stream_video_or_404),
) -> VideoRead:
    return VideoRead.model_validate(video)


@router.get(
    "/{video_id}/ask-status",
    response_model=AskStatus,
    description=(
        "Whether Ask is unlocked for this video. Signed-in users pay once per "
        "video when they start their first conversation; guests use a daily quota."
    ),
)
def get_ask_status(
    video=Depends(get_stream_video_or_404),
    db: Session = Depends(get_db),
    viewer: ViewerContext = Depends(get_viewer_context),
) -> AskStatus:
    if viewer.user_id is None:
        return AskStatus(unlocked=True, cost=0)
    return AskStatus(
        unlocked=credits_service.wiz_chat_unlocked(db, viewer.user_id, video.video_id),
        cost=settings.wiz_chat_cost,
    )


@router.get(
    "/{video_id}/transcript",
    response_model=TranscriptRead,
    description=(
        "The video's transcript segments. status is processing while the "
        "transcript is being fetched and unavailable when fetching failed."
    ),
)
@limiter.limit(settings.rate_limit_videos)
def get_transcript(
    request: Request,
    response: Response,
    video=Depends(get_stream_video_or_404),
    db: Session = Depends(get_db),
) -> TranscriptRead:
    return videos_service.get_transcript(db, video)


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
