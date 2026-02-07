from fastapi import APIRouter, Depends, Request, Response, status
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
    VideoNotesResponse,
)
from src.notes.schemas import NoteRead, NoteUpdate
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
    request: Request,
    response: Response,
    params: TaskPollParams = Depends(get_task_poll_params),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_token),
):
    task = internal_service.poll_for_task(
        db,
        params.task_type,
        params.timeout,
        params.poll_interval,
        params.max_retries,
        params.in_progress_timeout,
        worker_user_id=None,
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
    request: Request,
    response: Response,
    payload: TaskResultRequest,
    task_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_token),
) -> TaskSubmitResponse:
    task = internal_service.submit_task_result(
        db,
        task_id,
        payload.video_id,
        payload.success,
        payload.transcript,
        payload.metadata,
        payload.error_message,
        worker_user_id=None,
    )

    return TaskSubmitResponse(
        message="Task result submitted successfully",
        task_id=task.id,
        status=task.status.value,
    )


@router.get(
    "/videos/{video_id}/ai-notes",
    response_model=VideoNotesResponse,
    status_code=status.HTTP_200_OK,
    description="Fetch eligible notes for AI note generation.",
)
@limiter.exempt
def list_ai_notes(
    request: Request,
    response: Response,
    path: VideoIdPath = Depends(),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_token),
) -> VideoNotesResponse:
    video, notes = internal_service.fetch_ai_note_task_notes(db, path.video_id)
    if not video:
        raise NotFoundError("Video not found")
    if not notes:
        raise NotFoundError("No notes found for users with AI notes enabled")

    return VideoNotesResponse(
        video_id=path.video_id,
        notes=[NoteRead.model_validate(note) for note in notes],
        message="Successfully retrieved notes for AI note generation.",
    )


@router.post(
    "/videos/{video_id}/transcript",
    response_model=VideoRead,
    status_code=status.HTTP_200_OK,
    description="Store transcript data (upsert video).",
)
@limiter.exempt
def store_transcript(
    request: Request,
    response: Response,
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
    request: Request,
    response: Response,
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
    description="Store summary text (upsert video).",
)
@limiter.exempt
def store_summary(
    request: Request,
    response: Response,
    payload: SummaryWrite,
    path: VideoIdPath = Depends(),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_token),
) -> VideoRead:
    video = internal_service.store_summary(db, path.video_id, payload.summary)
    return VideoRead.model_validate(video)


@router.get(
    "/videos/{video_id}",
    response_model=VideoRead,
    status_code=status.HTTP_200_OK,
    description="Fetch video details (internal).",
)
@limiter.exempt
def get_video(
    request: Request,
    response: Response,
    path: VideoIdPath = Depends(),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_token),
) -> VideoRead:
    video = internal_service.get_video(db, path.video_id)
    if not video:
        raise NotFoundError("Video not found")
    return VideoRead.model_validate(video)


@router.patch(
    "/notes/{note_id}",
    response_model=NoteRead,
    status_code=status.HTTP_200_OK,
    description="Update note (internal).",
)
@limiter.exempt
def update_note(
    request: Request,
    response: Response,
    note_id: int,
    payload: NoteUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_token),
) -> NoteRead:
    note = internal_service.update_note(
        db,
        note_id,
        payload.text,
        payload.generated_by_ai,
    )
    if not note:
        raise NotFoundError("Note not found")
    return NoteRead.model_validate(note)
