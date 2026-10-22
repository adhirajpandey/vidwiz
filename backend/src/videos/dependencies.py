from typing import Annotated

from fastapi import Depends
from pydantic import AfterValidator
from sqlalchemy.orm import Session

from src.database import get_db
from src.exceptions import NotFoundError
from src.auth.dependencies import get_viewer_context
from src.videos import service as videos_service
from src.videos.schemas import VideoIdPath
from src.videos.utils import normalize_youtube_video_id


def get_video_id_path(
    video_id: Annotated[str, AfterValidator(normalize_youtube_video_id)],
) -> VideoIdPath:
    # Validating the path parameter here, rather than constructing VideoIdPath
    # from it, makes an invalid ID a normal 422 and lets auth dependencies run
    # first.
    return VideoIdPath(video_id=video_id)


def get_stream_video_or_404(
    path: VideoIdPath = Depends(get_video_id_path),
    db: Session = Depends(get_db),
    viewer=Depends(get_viewer_context),
):
    _ = viewer
    video = videos_service.get_video_by_id(db, path.video_id)
    if not video:
        raise NotFoundError("Video not found")
    return video
