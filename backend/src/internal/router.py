from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from src.database import get_db
from src.exceptions import NotFoundError
from src.internal import service as internal_service
from src.internal.dependencies import get_task_poll_params, require_admin_token
from src.internal.schemas import (
    MetadataWrite,
    SummaryWrite,
    TaskPollParams,
    TaskResultRequest,
    TaskRetrievedResponse,
    TaskSubmitResponse,
    TranscriptWrite,
    MomentAiWrite,
    PendingMoment,
    PendingMomentsResponse,
)
from src.moments import service as moments_service
from src.moments.models import Moment
from src.moments.schemas import MomentRead
from src.shared.ratelimit import limiter
from src.videos.schemas import VideoIdPath, VideoRead


router = APIRouter(prefix="/v2/internal", tags=["Internal"])


@router.get(
    "/tasks",
    response_model=TaskRetrievedResponse,
    status_code=status.HTTP_200_OK,
    description="Poll for work items.",
)
@limiter.exempt
def get_task(
    params: TaskPollParams = Depends(get_task_poll_params),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_token),
):
    task = internal_service.poll_for_task(
        db,
        params.task_type,
        params.timeout,
    )
    if not task:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return TaskRetrievedResponse(
        task_id=task.id,
        task_type=task.task_type,
        task_details=task.task_details,
        retry_count=task.retry_count,
        message="Task retrieved successfully",
    )


@router.post(
    "/tasks/{task_id}/result",
    response_model=TaskSubmitResponse,
    status_code=status.HTTP_200_OK,
    description="Submit task result.",
)
@limiter.exempt
def submit_task_result(
    payload: TaskResultRequest,
    task_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_token),
) -> TaskSubmitResponse:
    task = internal_service.submit_task_result(db, task_id, payload)

    return TaskSubmitResponse(
        message="Task result submitted successfully",
        task_id=task.id,
        status=task.status.value,
    )


@router.post(
    "/videos/{video_id}/pending-moments",
    response_model=PendingMomentsResponse,
    status_code=status.HTTP_200_OK,
    description=(
        "Charge and mark queued the moments waiting for this video's transcript. "
        "Called by the dispatcher after the transcript upload."
    ),
)
@limiter.exempt
def collect_pending_moments(
    path: VideoIdPath = Depends(),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_token),
) -> PendingMomentsResponse:
    moments = moments_service.collect_pending_ai(db, path.video_id)
    return PendingMomentsResponse(
        video_id=path.video_id,
        moments=[PendingMoment.model_validate(moment) for moment in moments],
    )


@router.post(
    "/videos/{video_id}/transcript",
    response_model=VideoRead,
    status_code=status.HTTP_200_OK,
    description="Store transcript data (upsert video).",
)
@limiter.exempt
def store_transcript(
    payload: TranscriptWrite,
    path: VideoIdPath = Depends(),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_token),
) -> VideoRead:
    video = internal_service.store_transcript(db, path.video_id, payload.transcript)
    return VideoRead.model_validate(video)


@router.post(
    "/videos/{video_id}/metadata",
    response_model=VideoRead,
    status_code=status.HTTP_200_OK,
    description="Store metadata data (upsert video).",
)
@limiter.exempt
def store_metadata(
    payload: MetadataWrite,
    path: VideoIdPath = Depends(),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_token),
) -> VideoRead:
    video = internal_service.store_metadata(db, path.video_id, payload.metadata)
    return VideoRead.model_validate(video)


@router.post(
    "/videos/{video_id}/summary",
    response_model=VideoRead,
    status_code=status.HTTP_200_OK,
    description="Store summary text and optional miscellaneous data (upsert video).",
)
@limiter.exempt
def store_summary(
    payload: SummaryWrite,
    path: VideoIdPath = Depends(),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_token),
) -> VideoRead:
    video = internal_service.store_summary(
        db,
        path.video_id,
        payload.summary,
        (
            payload.miscellaneous_data.model_dump(exclude_none=True)
            if payload.miscellaneous_data is not None
            else None
        ),
    )
    return VideoRead.model_validate(video)


@router.get(
    "/videos/{video_id}",
    response_model=VideoRead,
    status_code=status.HTTP_200_OK,
    description="Fetch video details (internal).",
)
@limiter.exempt
def get_video(
    path: VideoIdPath = Depends(),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_token),
) -> VideoRead:
    video = internal_service.get_video(db, path.video_id)
    if not video:
        raise NotFoundError("Video not found")
    return VideoRead.model_validate(video)


@router.put(
    "/moments/{moment_id}/ai",
    response_model=MomentRead,
    status_code=status.HTTP_200_OK,
    description="Store the AI line generated for a moment (internal).",
)
@limiter.exempt
def store_moment_ai(
    moment_id: int,
    payload: MomentAiWrite,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_token),
) -> MomentRead:
    moment = db.get(Moment, moment_id)
    if not moment:
        raise NotFoundError("Moment not found")
    return MomentRead.model_validate(
        moments_service.save_ai_text(db, moment, payload.ai_text)
    )
