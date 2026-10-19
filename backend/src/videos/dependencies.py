from fastapi import Depends
from sqlalchemy.orm import Session

from src.database import get_db
from src.exceptions import NotFoundError
from src.auth.dependencies import get_viewer_context
from src.videos import service as videos_service
from src.videos.schemas import VideoIdPath


def get_stream_video_or_404(
    path: VideoIdPath = Depends(),
    db: Session = Depends(get_db),
    viewer=Depends(get_viewer_context),
):
    _ = viewer
    video = videos_service.get_video_by_id(db, path.video_id)
    if not video:
        raise NotFoundError("Video not found")
    return video
