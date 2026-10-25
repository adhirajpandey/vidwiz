from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from src.auth.dependencies import (
    get_current_user_id,
    get_current_user_id_or_api_token,
)
from src.database import get_db
from src.exceptions import BadRequestError, NotFoundError
from src.models import MessageResponse
from src.moments import export
from src.moments import service as moments_service
from src.moments.dependencies import get_moment_or_404
from src.moments.models import CaptureSource, Moment
from src.moments.schemas import (
    CaptureCreate,
    CaptureResponse,
    LegacyNoteCreate,
    MomentFeed,
    MomentRead,
    MomentUpdate,
    PassageSave,
    ResolveChoice,
    ResurfaceResponse,
    parse_seconds,
)
from src.videos import service as videos_service
from src.videos.dependencies import get_video_id_path
from src.videos.schemas import VideoIdPath

router = APIRouter(prefix="/v2", tags=["Moments"])


@router.post(
    "/captures",
    response_model=CaptureResponse,
    status_code=status.HTTP_201_CREATED,
    description=(
        "Capture a moment from any client. Send a video URL or ID, or a title when "
        "the client cannot see the ID. A capture within 10 seconds of an existing "
        "moment on the same video merges into it and returns 200. Accepts a web "
        "session JWT or a personal API token."
    ),
)
def create_capture(
    payload: CaptureCreate,
    response: Response,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id_or_api_token),
) -> CaptureResponse:
    moment, merged = moments_service.capture(db, user_id, payload)
    if merged:
        response.status_code = status.HTTP_200_OK
    return CaptureResponse(moment=MomentRead.model_validate(moment), merged=merged)


@router.post(
    "/moments/passages",
    response_model=CaptureResponse,
    status_code=status.HTTP_201_CREATED,
    description=(
        "Save a cited passage (from an answer or the transcript) as a moment. "
        "Free: no AI line and no credits. Merges into a moment within 10 "
        "seconds and returns 200."
    ),
)
def save_passage(
    payload: PassageSave,
    response: Response,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> CaptureResponse:
    moment, merged = moments_service.save_passage(db, user_id, payload)
    if merged:
        response.status_code = status.HTTP_200_OK
    return CaptureResponse(moment=MomentRead.model_validate(moment), merged=merged)


@router.get(
    "/moments",
    response_model=MomentFeed,
    description="Recent moments across the library, newest first.",
)
def list_recent_moments(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> MomentFeed:
    return moments_service.feed(db, user_id, page, per_page)


@router.get(
    "/moments/resurface",
    response_model=ResurfaceResponse,
    description="One resolved moment older than 60 days, in stable daily order.",
)
def resurface_moment(
    skip: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> ResurfaceResponse:
    return moments_service.resurface(db, user_id, skip)


@router.get(
    "/videos/{video_id}/moments",
    response_model=list[MomentRead],
    description="The user's moments for a video, in playback order.",
)
def list_video_moments(
    path: VideoIdPath = Depends(get_video_id_path),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> list[MomentRead]:
    moments = moments_service.list_for_video(db, user_id, path.video_id)
    return [MomentRead.model_validate(moment) for moment in moments]


@router.patch(
    "/moments/{moment_id}",
    response_model=MomentRead,
    description="Edit a moment's note or AI line. Send null to clear a field.",
)
def update_moment(
    payload: MomentUpdate,
    db: Session = Depends(get_db),
    moment: Moment = Depends(get_moment_or_404),
) -> MomentRead:
    fields = payload.model_dump(include=payload.model_fields_set)
    if not fields:
        raise BadRequestError("No fields provided for update")
    return MomentRead.model_validate(moments_service.update(db, moment, fields))


@router.post(
    "/moments/{moment_id}/ai",
    response_model=MomentRead,
    description="Request an AI line for an existing moment. Charged once per moment.",
)
def request_moment_ai(
    db: Session = Depends(get_db),
    moment: Moment = Depends(get_moment_or_404),
) -> MomentRead:
    return MomentRead.model_validate(moments_service.request_ai(db, moment))


@router.post(
    "/moments/{moment_id}/resolve",
    response_model=MomentRead,
    description=(
        "Pick the video for a title capture that matched several videos. "
        "Returns the resolved moment, or the moment it merged into."
    ),
)
def resolve_moment(
    payload: ResolveChoice,
    db: Session = Depends(get_db),
    moment: Moment = Depends(get_moment_or_404),
) -> MomentRead:
    return MomentRead.model_validate(
        moments_service.choose_candidate(db, moment, payload.video_id)
    )


@router.delete("/moments/{moment_id}", response_model=MessageResponse)
def delete_moment(
    db: Session = Depends(get_db),
    moment: Moment = Depends(get_moment_or_404),
) -> MessageResponse:
    moments_service.delete(db, moment)
    return MessageResponse(message="Moment deleted")


@router.post(
    "/videos/{video_id}/notes",
    response_model=MomentRead,
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
    description=(
        "Compatibility route for the published 2.x extension. Remove once the "
        "3.x extension is live in the store."
    ),
)
def create_legacy_note(
    payload: LegacyNoteCreate,
    path: VideoIdPath = Depends(get_video_id_path),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id_or_api_token),
) -> MomentRead:
    try:
        at = parse_seconds(payload.timestamp)
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc
    capture = CaptureCreate(
        video=path.video_id,
        title=payload.video_title,
        at=at,
        note=payload.text,
        # 2.x semantics: an empty note asks for an AI line if the user allows it.
        ai=None if payload.text is None else False,
        source=CaptureSource.EXTENSION,
    )
    moment, _ = moments_service.capture(db, user_id, capture)
    return MomentRead.model_validate(moment)


@router.get(
    "/videos/{video_id}/export.md",
    response_class=PlainTextResponse,
    description="The user's moments for a video as Markdown.",
)
def export_video(
    path: VideoIdPath = Depends(get_video_id_path),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> PlainTextResponse:
    video = videos_service.get_video_by_id(db, path.video_id)
    if video is None:
        raise NotFoundError("Video not found")
    return _markdown(export.video_markdown(db, user_id, video), path.video_id)


@router.get(
    "/library/export.md",
    response_class=PlainTextResponse,
    description="All of the user's moments, grouped by saved video, as Markdown.",
)
def export_library(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
) -> PlainTextResponse:
    return _markdown(export.library_markdown(db, user_id), "vidwiz-library")


def _markdown(content: str, name: str) -> PlainTextResponse:
    return PlainTextResponse(
        content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}.md"'},
    )
