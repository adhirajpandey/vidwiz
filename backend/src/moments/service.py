import logging
from collections import Counter
from collections.abc import Callable
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy import update as sql_update
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from src import database, transcripts
from src.auth import service as auth_service
from src.auth.models import User
from src.config import settings
from src.credits import service as credits_service
from src.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from src.internal import constants as internal_constants
from src.internal.models import Task, TaskStatus
from src.internal.scheduling import prepare_video
from src.library import service as library_service
from src.library.models import LibraryItem
from src.logging import current_correlation_id, log_event
from src.metrics import record_workflow_event
from src.shared.queues import send_job
from src.moments.models import AiStatus, CaptureSource, Moment, ResolveStatus
from src.moments.schemas import (
    CaptureCreate,
    FeedMoment,
    MomentFeed,
    MomentRead,
    PassageSave,
    ResurfaceFound,
    ResurfaceNone,
    ResurfaceResponse,
)
from src.videos import service as videos_service
from src.videos.models import TranscriptStatus, Video
from src.videos.utils import capture_past_end, video_duration

logger = logging.getLogger(__name__)

# Captures this close to an existing moment on the same video join it.
DEDUPE_WINDOW_SECONDS = 10

# The text a moment's embedding is made from; changing it clears the embedding.
MOMENT_TEXT_FIELDS = {"note", "ai_text", "quote"}

# AI can be requested again from these states without a new charge.
AI_REQUESTABLE = {
    AiStatus.NOT_REQUESTED,
    AiStatus.FAILED,
    AiStatus.INSUFFICIENT_CREDITS,
    AiStatus.NO_TRANSCRIPT,
}


def capture(
    db: Session,
    user_id: int,
    payload: CaptureCreate,
    run_later: Callable[..., None],
) -> tuple[Moment, bool]:
    """Save a capture as a new moment or merge it into a nearby one.

    The AI job goes through `run_later`, so the saved moment does not wait on SQS.
    """
    user = db.get(User, user_id)
    wants_ai = payload.ai if payload.ai is not None else _ai_default(user)
    logger.debug(
        "Capturing moment",
        extra={
            "user_id": user_id,
            "has_video": payload.video is not None,
            "source": payload.source.value,
            "wants_ai": wants_ai,
        },
    )

    video_id = payload.video or _recent_video_by_title(db, user_id, payload.title)
    if video_id is None:
        moment = _capture_unresolved(db, user_id, payload, wants_ai)
        return moment, False

    known_video = videos_service.get_video_by_id(db, video_id)
    if known_video:
        validate_capture_time(known_video, payload.at)
    prepare_video(db, video_id, payload.title)
    library_service.save_video(db, user_id, video_id)

    existing = _find_nearby(db, user_id, video_id, payload.at)
    if existing is not None:
        previous_ai_status = existing.ai_status
        enqueue = _merge(db, existing, payload.note, wants_ai)
        db.commit()
        db.refresh(existing)
        _record_ai_request_outcome(existing, wants_ai, enqueue, previous_ai_status)
        if enqueue:
            run_later(send_ai_job, queue_payload(existing))
        return existing, True

    moment = Moment(
        user_id=user_id,
        video_id=video_id,
        at_seconds=payload.at,
        note=payload.note,
        source=payload.source,
        resolve_status=ResolveStatus.RESOLVED,
        ai_status=AiStatus.NOT_REQUESTED,
    )
    db.add(moment)
    db.flush()
    previous_ai_status = moment.ai_status
    enqueue = _attach_transcript_work(db, moment, wants_ai)
    db.commit()
    db.refresh(moment)
    _record_ai_request_outcome(moment, wants_ai, enqueue, previous_ai_status)
    if enqueue:
        run_later(send_ai_job, queue_payload(moment))
    return moment, False


def _ai_default(user: User | None) -> bool:
    return auth_service.ai_moments_default(user) if user else False


def _recent_video_by_title(db: Session, user_id: int, title: str | None) -> str | None:
    """Phones send titles; a video already in the library resolves instantly."""
    if not title:
        return None
    return db.execute(
        select(Video.video_id)
        .join(LibraryItem, LibraryItem.video_id == Video.video_id)
        .where(
            LibraryItem.user_id == user_id,
            func.lower(Video.title) == title.lower(),
        )
        .order_by(LibraryItem.added_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _capture_unresolved(
    db: Session, user_id: int, payload: CaptureCreate, wants_ai: bool
) -> Moment:
    moment = Moment(
        user_id=user_id,
        video_id=None,
        at_seconds=payload.at,
        note=payload.note,
        source=payload.source,
        resolve_status=ResolveStatus.RESOLVING,
        # The AI line waits for the video, then for its transcript.
        ai_status=AiStatus.WAITING_TRANSCRIPT if wants_ai else AiStatus.NOT_REQUESTED,
        pending_title=payload.title,
        pending_channel=payload.channel,
    )
    db.add(moment)
    db.flush()
    db.add(
        Task(
            task_type=internal_constants.RESOLVE_TITLE_TASK_TYPE,
            status=TaskStatus.PENDING,
            task_details={
                "moment_id": moment.id,
                "title": payload.title,
                "channel": payload.channel,
                **(
                    {"correlation_id": current_correlation_id()}
                    if current_correlation_id()
                    else {}
                ),
            },
        )
    )
    db.commit()
    db.refresh(moment)
    record_workflow_event("title_resolution", "task_queued")
    if wants_ai:
        record_workflow_event("ai_moment", "ai_waiting_transcript")
    logger.debug("Queued title resolution", extra={"moment_id": moment.id})
    return moment


def _find_nearby(
    db: Session, user_id: int, video_id: str, at_seconds: int
) -> Moment | None:
    distance = func.abs(Moment.at_seconds - at_seconds)
    return db.execute(
        select(Moment)
        .where(
            Moment.user_id == user_id,
            Moment.video_id == video_id,
            distance <= DEDUPE_WINDOW_SECONDS,
        )
        .order_by(distance, Moment.id)
        .limit(1)
    ).scalar_one_or_none()


def _merge(db: Session, moment: Moment, note: str | None, wants_ai: bool) -> bool:
    logger.debug("Merging capture into moment", extra={"moment_id": moment.id})
    if note:
        moment.note = f"{moment.note}\n{note}" if moment.note else note
        moment.embedding = None
    if wants_ai and moment.ai_status in AI_REQUESTABLE:
        return _request_ai(db, moment)
    return False


def _attach_transcript_work(db: Session, moment: Moment, wants_ai: bool) -> bool:
    """Add the quote now if the transcript exists, and request AI if wanted."""
    video = videos_service.get_video_by_id(db, moment.video_id)
    if video and video.has_transcript:
        transcript = transcripts.load_transcript(moment.video_id)
        if transcript:
            apply_quote(moment, transcript)
    if wants_ai:
        return _request_ai(db, moment)
    return False


def validate_capture_time(video: Video, at_seconds: float) -> None:
    if capture_past_end(video.video_metadata, at_seconds):
        raise BadRequestError(
            f"Capture time {at_seconds:g}s is past the video's end "
            f"({video_duration(video.video_metadata):g}s). Choose a time within the video."
        )


def flag_invalid_captures(db: Session, video: Video) -> int:
    """Metadata can arrive after capture. Keep the note and stop pending AI."""
    duration = video_duration(video.video_metadata)
    if duration is None:
        return 0
    result = db.execute(
        sql_update(Moment)
        .where(
            Moment.video_id == video.video_id,
            Moment.at_seconds > duration,
            Moment.ai_status.in_(
                [
                    AiStatus.NOT_REQUESTED,
                    AiStatus.WAITING_TRANSCRIPT,
                    AiStatus.QUEUED,
                    AiStatus.FAILED,
                    AiStatus.NO_TRANSCRIPT,
                    AiStatus.INSUFFICIENT_CREDITS,
                ]
            ),
        )
        .values(ai_status=AiStatus.INVALID_TIMESTAMP, updated_at=Moment.updated_at)
    )
    return result.rowcount


def _request_ai(db: Session, moment: Moment) -> bool:
    """Set the AI status for a request. Returns True when the job should be sent."""
    video = videos_service.get_video_by_id(db, moment.video_id)
    if video is not None and capture_past_end(video.video_metadata, moment.at_seconds):
        moment.ai_status = AiStatus.INVALID_TIMESTAMP
        return False
    if video is not None and video.transcript_status == TranscriptStatus.UNAVAILABLE:
        moment.ai_status = AiStatus.NO_TRANSCRIPT
        return False
    if video is None or not video.has_transcript:
        moment.ai_status = AiStatus.WAITING_TRANSCRIPT
        return False
    db.flush()
    try:
        credits_service.charge_ai_moment(db, moment.user_id, moment.id)
    except ForbiddenError:
        moment.ai_status = AiStatus.INSUFFICIENT_CREDITS
        return False
    moment.ai_status = AiStatus.QUEUED
    return True


def _record_ai_request_outcome(
    moment: Moment,
    requested: bool,
    enqueue: bool,
    previous_status: AiStatus,
) -> None:
    """Count one committed AI status transition, never a repeated unchanged state."""
    if not requested:
        return
    if enqueue:
        record_workflow_event("ai_moment", "ai_queued")
    elif moment.ai_status != previous_status:
        events = {
            AiStatus.WAITING_TRANSCRIPT: ("ai_waiting_transcript", "none"),
            AiStatus.INSUFFICIENT_CREDITS: (
                "ai_insufficient_credits",
                "insufficient_credits",
            ),
            AiStatus.NO_TRANSCRIPT: ("ai_no_transcript", "no_transcript"),
        }
        event = events.get(moment.ai_status)
        if event:
            record_workflow_event("ai_moment", event[0], event[1])


def save_passage(
    db: Session, user_id: int, payload: PassageSave
) -> tuple[Moment, bool]:
    """Keep a cited passage as a moment, with the cited text as its quote."""
    video = videos_service.get_video_by_id(db, payload.video_id)
    if video is None:
        raise NotFoundError("Video not found")
    validate_capture_time(video, payload.end_seconds)
    start = int(payload.start_seconds)
    library_service.save_video(db, user_id, payload.video_id)
    existing = _find_nearby(db, user_id, payload.video_id, start)
    if existing is not None:
        _merge(db, existing, payload.note, wants_ai=False)
        db.commit()
        db.refresh(existing)
        return existing, True

    transcript = (
        transcripts.load_transcript(payload.video_id) if video.has_transcript else None
    )
    moment = Moment(
        user_id=user_id,
        video_id=payload.video_id,
        at_seconds=start,
        quote=(
            transcripts.text_between(
                transcript, payload.start_seconds, payload.end_seconds
            )
            if transcript
            else None
        ),
        quote_start_seconds=start,
        note=payload.note,
        source=CaptureSource.WEB,
        resolve_status=ResolveStatus.RESOLVED,
        ai_status=AiStatus.NOT_REQUESTED,
    )
    db.add(moment)
    db.commit()
    db.refresh(moment)
    logger.debug("Saved passage as moment", extra={"moment_id": moment.id})
    return moment, False


def apply_quote(moment: Moment, transcript: list) -> None:
    quote = transcripts.quote_for(transcript, moment.at_seconds)
    if quote:
        if quote[0] != moment.quote:
            moment.embedding = None
        moment.quote, moment.quote_start_seconds = quote


def queue_payload(moment: Moment) -> dict:
    """The AI moment job, shared with the dispatcher's pending-moments reply."""
    payload = {
        "id": moment.id,
        "video_id": moment.video_id,
        "at_seconds": moment.at_seconds,
        "user_id": moment.user_id,
    }
    correlation_id = current_correlation_id()
    if correlation_id:
        payload["correlation_id"] = correlation_id
    return payload


def push_moment_to_sqs(db: Session, moment: Moment) -> None:
    try:
        send_job(settings.sqs_ai_note_queue_url, queue_payload(moment))
        logger.info("Queued AI moment", extra={"moment_id": moment.id})
        log_event("moment_ai.queued", user_id=moment.user_id, moment_id=moment.id)
    except Exception as exc:
        # The charge stays recorded once, so a retry does not charge again.
        logger.error(
            "Failed to queue AI moment",
            extra={"moment_id": moment.id, "error": str(exc)},
        )
        log_event(
            "moment_ai.failed",
            user_id=moment.user_id,
            moment_id=moment.id,
            reason="queue_error",
        )
        moment.ai_status = AiStatus.FAILED
        db.commit()
        record_workflow_event("ai_moment", "ai_failed", "queue_error")


def send_ai_job(payload: dict) -> None:
    """Send a capture's AI job after its response, on a session of its own."""
    try:
        send_job(settings.sqs_ai_note_queue_url, payload)
        logger.info("Queued AI moment", extra={"moment_id": payload["id"]})
        log_event(
            "moment_ai.queued", user_id=payload["user_id"], moment_id=payload["id"]
        )
    except Exception as exc:
        # The charge stays recorded once, so a retry does not charge again.
        logger.error(
            "Failed to queue AI moment",
            extra={"moment_id": payload["id"], "error": str(exc)},
        )
        log_event(
            "moment_ai.failed",
            user_id=payload["user_id"],
            moment_id=payload["id"],
            reason="queue_error",
        )
        db = database.SessionLocal()
        try:
            result = db.execute(
                sql_update(Moment)
                .where(Moment.id == payload["id"], Moment.ai_status == AiStatus.QUEUED)
                .values(ai_status=AiStatus.FAILED)
            )
            db.commit()
            if result.rowcount:
                record_workflow_event("ai_moment", "ai_failed", "queue_error")
        finally:
            db.close()


def request_ai(db: Session, moment: Moment) -> Moment:
    if moment.resolve_status != ResolveStatus.RESOLVED:
        raise BadRequestError("The video for this moment is not resolved yet")
    if moment.ai_status not in AI_REQUESTABLE:
        raise BadRequestError("An AI line is already requested or ready")
    previous_ai_status = moment.ai_status
    enqueue = _request_ai(db, moment)
    db.commit()
    db.refresh(moment)
    _record_ai_request_outcome(moment, True, enqueue, previous_ai_status)
    if enqueue:
        push_moment_to_sqs(db, moment)
        db.refresh(moment)
    return moment


def complete_resolution(
    db: Session, moment: Moment, video_id: str, title: str | None
) -> None:
    """Resolve a title capture and recover earlier matching lookup failures."""
    failed = []
    if moment.pending_title:
        failed = db.scalars(
            select(Moment)
            .where(
                Moment.user_id == moment.user_id,
                Moment.id < moment.id,
                Moment.video_id.is_(None),
                Moment.resolve_status == ResolveStatus.UNRESOLVED,
                func.lower(func.trim(Moment.pending_title))
                == moment.pending_title.strip().lower(),
                Moment.pending_channel == moment.pending_channel,
            )
            .order_by(Moment.id)
        ).all()
        # Ambiguous captures still need the user's choice.
        failed = [capture for capture in failed if not capture.resolve_candidates]

    _attach_resolved_video(db, moment, video_id, title)
    for capture in failed:
        _attach_resolved_video(db, capture, video_id, title)


def _attach_resolved_video(
    db: Session, moment: Moment, video_id: str, title: str | None
) -> None:
    logger.debug(
        "Resolved moment video", extra={"moment_id": moment.id, "video_id": video_id}
    )
    # A final title-lookup failure marks a pending AI request FAILED. The
    # capture still has no video, so no AI job or charge has happened yet.
    wants_ai = moment.ai_status in {AiStatus.WAITING_TRANSCRIPT, AiStatus.FAILED}
    prepare_video(db, video_id, title)
    library_service.save_video(db, moment.user_id, video_id)

    video = videos_service.get_video_by_id(db, video_id)
    invalid = video is not None and capture_past_end(
        video.video_metadata, moment.at_seconds
    )
    existing = (
        None
        if invalid
        else _find_nearby(db, moment.user_id, video_id, moment.at_seconds)
    )
    if existing is not None:
        previous_ai_status = existing.ai_status
        enqueue = _merge(db, existing, moment.note, wants_ai)
        db.delete(moment)
        db.commit()
        record_workflow_event("title_resolution", "title_resolved")
        _record_ai_request_outcome(existing, wants_ai, enqueue, previous_ai_status)
        if enqueue:
            push_moment_to_sqs(db, existing)
        return

    moment.video_id = video_id
    moment.resolve_status = ResolveStatus.RESOLVED
    moment.pending_title = None
    moment.pending_channel = None
    previous_ai_status = moment.ai_status
    moment.ai_status = AiStatus.NOT_REQUESTED
    enqueue = _attach_transcript_work(db, moment, wants_ai)
    if invalid:
        moment.ai_status = AiStatus.INVALID_TIMESTAMP
    db.commit()
    record_workflow_event("title_resolution", "title_resolved")
    _record_ai_request_outcome(moment, wants_ai, enqueue, previous_ai_status)
    if enqueue:
        push_moment_to_sqs(db, moment)


def offer_candidates(db: Session, moment: Moment, candidates: list[dict]) -> None:
    """The title matched several videos; keep them so the user can pick."""
    logger.debug(
        "Title capture needs a choice",
        extra={"moment_id": moment.id, "candidates": len(candidates)},
    )
    moment.resolve_status = ResolveStatus.UNRESOLVED
    moment.resolve_candidates = candidates
    db.commit()
    record_workflow_event("title_resolution", "title_candidates_offered")


def choose_candidate(db: Session, moment: Moment, video_id: str) -> Moment:
    """Resolve an unresolved title capture to the video the user picked."""
    if moment.resolve_status != ResolveStatus.UNRESOLVED:
        raise BadRequestError("This moment does not need a video choice")
    candidates = moment.resolve_candidates or []
    chosen = next((c for c in candidates if c.get("video_id") == video_id), None)
    if chosen is None:
        raise BadRequestError("Pick one of the suggested videos")
    moment.resolve_status = ResolveStatus.RESOLVING
    moment.resolve_candidates = None
    db.flush()
    moment_id, user_id, at_seconds = moment.id, moment.user_id, moment.at_seconds
    complete_resolution(db, moment, video_id, chosen.get("title"))
    merged_into = get_for_user(db, user_id, moment_id)
    if merged_into is not None:
        return merged_into
    # The capture merged into an existing nearby moment.
    return _find_nearby(db, user_id, video_id, at_seconds)


def fail_resolution(db: Session, moment: Moment) -> None:
    logger.debug("Title resolution failed", extra={"moment_id": moment.id})
    moment.resolve_status = ResolveStatus.UNRESOLVED
    ai_failed = moment.ai_status == AiStatus.WAITING_TRANSCRIPT
    if ai_failed:
        moment.ai_status = AiStatus.FAILED
    user_id, moment_id = moment.user_id, moment.id
    db.commit()
    record_workflow_event("title_resolution", "title_failed", "title_unresolved")
    if ai_failed:
        record_workflow_event("ai_moment", "ai_failed", "title_unresolved")
        log_event(
            "moment_ai.failed",
            user_id=user_id,
            moment_id=moment_id,
            reason="title_unresolved",
        )


def on_transcript_stored(
    db: Session, video_id: str, transcript: list, *, recompute_all: bool = False
) -> None:
    """Fill missing quotes, or recompute all quotes when explicitly requested.

    A filled quote is not the user's activity, so `updated_at` (which orders the
    library) keeps its value.
    """
    query = select(Moment).where(Moment.video_id == video_id)
    if not recompute_all:
        query = query.where(Moment.quote.is_(None))
    moments = db.execute(query).scalars().all()
    for moment in moments:
        updated_at = moment.updated_at
        quote = moment.quote
        if recompute_all:
            moment.quote = moment.quote_start_seconds = None
        apply_quote(moment, transcript)
        if moment.quote != quote:
            moment.embedding = None
        moment.updated_at = updated_at
        # Setting the same value is not a change on its own; without this flag
        # the column's onupdate would stamp the current time.
        flag_modified(moment, "updated_at")
    logger.debug(
        "Filled moment quotes", extra={"video_id": video_id, "count": len(moments)}
    )


def on_transcript_unavailable(db: Session, video_id: str) -> int:
    waiting = (
        db.execute(
            select(Moment).where(
                Moment.video_id == video_id,
                Moment.ai_status == AiStatus.WAITING_TRANSCRIPT,
            )
        )
        .scalars()
        .all()
    )
    for moment in waiting:
        moment.ai_status = AiStatus.NO_TRANSCRIPT
    logger.debug(
        "Marked moments without transcript",
        extra={"video_id": video_id, "count": len(waiting)},
    )
    return len(waiting)


def collect_pending_ai(db: Session, video_id: str) -> list[Moment]:
    """Charge and mark queued the moments waiting for this video's transcript.

    Called by the dispatcher after the transcript upload. Owners without
    credits get an explicit insufficient_credits status. Queued moments are
    returned again without charging, so a lost response can be retried.
    """
    video = db.execute(
        select(Video).where(Video.video_id == video_id)
    ).scalar_one_or_none()
    if video is not None and video.transcript_status == TranscriptStatus.PENDING:
        raise ConflictError("Transcript is still being processed")

    waiting = (
        db.execute(
            select(Moment)
            .where(
                Moment.video_id == video_id,
                Moment.ai_status.in_([AiStatus.WAITING_TRANSCRIPT, AiStatus.QUEUED]),
            )
            .order_by(Moment.created_at.asc(), Moment.id.asc())
        )
        .scalars()
        .all()
    )
    if video:
        flag_invalid_captures(db, video)
    queued = []
    newly_queued = []
    newly_unavailable: Counter = Counter()
    for moment in waiting:
        if moment.ai_status == AiStatus.INVALID_TIMESTAMP:
            continue
        if moment.ai_status == AiStatus.QUEUED:
            queued.append(moment)
        else:
            previous_ai_status = moment.ai_status
            if _request_ai(db, moment):
                queued.append(moment)
                newly_queued.append((moment.user_id, moment.id))
            elif moment.ai_status != previous_ai_status:
                newly_unavailable[moment.ai_status] += 1
    db.commit()
    # Moments that were already queued got their event when they were queued.
    for user_id, moment_id in newly_queued:
        log_event("moment_ai.queued", user_id=user_id, moment_id=moment_id)
        record_workflow_event("ai_moment", "ai_queued")
    if newly_unavailable[AiStatus.INSUFFICIENT_CREDITS]:
        record_workflow_event(
            "ai_moment",
            "ai_insufficient_credits",
            "insufficient_credits",
            newly_unavailable[AiStatus.INSUFFICIENT_CREDITS],
        )
    if newly_unavailable[AiStatus.NO_TRANSCRIPT]:
        record_workflow_event(
            "ai_moment",
            "ai_no_transcript",
            "no_transcript",
            newly_unavailable[AiStatus.NO_TRANSCRIPT],
        )
    return queued


def save_ai_text(
    db: Session, moment: Moment, ai_text: str | None, ai_model: str | None = None
) -> Moment:
    """Store the worker result; null marks a queued generation as failed."""
    video = videos_service.get_video_by_id(db, moment.video_id)
    if moment.ai_status == AiStatus.INVALID_TIMESTAMP or (
        moment.ai_status != AiStatus.READY
        and video is not None
        and capture_past_end(video.video_metadata, moment.at_seconds)
    ):
        moment.ai_status = AiStatus.INVALID_TIMESTAMP
        db.commit()
        db.refresh(moment)
        return moment
    was_queued = moment.ai_status == AiStatus.QUEUED
    ai_failed = not ai_text and was_queued
    if ai_text:
        if ai_text != moment.ai_text:
            moment.embedding = None
        moment.ai_text = ai_text
        moment.ai_model = ai_model
        moment.ai_status = AiStatus.READY
    elif ai_failed:
        moment.ai_status = AiStatus.FAILED
    db.commit()
    db.refresh(moment)
    if was_queued and ai_text:
        record_workflow_event("ai_moment", "ai_ready")
    elif ai_failed:
        record_workflow_event("ai_moment", "ai_failed", "worker_error")
    if ai_text:
        log_event(
            "moment_ai.completed",
            user_id=moment.user_id,
            moment_id=moment.id,
            model=ai_model,
        )
    elif ai_failed:
        log_event(
            "moment_ai.failed",
            user_id=moment.user_id,
            moment_id=moment.id,
            reason="worker_failed",
        )
    return moment


def sweep_stale_ai(db: Session, older_than: timedelta) -> int:
    """Fail AI lines queued longer than any worker attempt can take.

    The worker reports its own failures; this covers jobs whose report never
    arrived. A failed line can be requested again without a new charge.
    """
    failed = db.execute(
        sql_update(Moment)
        .where(
            Moment.ai_status == AiStatus.QUEUED,
            Moment.updated_at < func.now() - older_than,
        )
        .values(ai_status=AiStatus.FAILED)
        .returning(Moment.id, Moment.user_id)
    ).all()
    db.commit()
    if failed:
        record_workflow_event("ai_moment", "ai_failed", "stale", len(failed))
    for moment_id, user_id in failed:
        log_event(
            "moment_ai.failed", user_id=user_id, moment_id=moment_id, reason="stale"
        )
    return len(failed)


def list_for_video(db: Session, user_id: int, video_id: str) -> list[Moment]:
    return (
        db.execute(
            select(Moment)
            .where(Moment.user_id == user_id, Moment.video_id == video_id)
            .order_by(Moment.at_seconds.asc(), Moment.id.asc())
        )
        .scalars()
        .all()
    )


def feed(db: Session, user_id: int, page: int, per_page: int) -> MomentFeed:
    """Recent moments across the library, newest first."""
    rows = db.execute(
        select(Moment, Video.title, Video.video_metadata)
        .outerjoin(Video, Video.video_id == Moment.video_id)
        .where(Moment.user_id == user_id)
        .order_by(Moment.created_at.desc(), Moment.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page + 1)
    ).all()
    items = [
        FeedMoment(
            **MomentRead.model_validate(moment).model_dump(),
            video_title=title,
            video_metadata=metadata,
        )
        for moment, title, metadata in rows[:per_page]
    ]
    return MomentFeed(
        moments=items, page=page, per_page=per_page, has_more=len(rows) > per_page
    )


def resurface(db: Session, user_id: int, skip: int = 0) -> ResurfaceResponse:
    """One older moment in a stable daily order; skip walks that order."""
    lead = func.coalesce(
        func.nullif(func.trim(Moment.ai_text), ""),
        func.nullif(func.trim(Moment.note), ""),
        func.nullif(func.trim(Moment.quote), ""),
        "",
    )
    row = db.execute(
        select(Moment, Video.title, Video.video_metadata)
        .join(Video, Video.video_id == Moment.video_id)
        .where(
            Moment.user_id == user_id,
            Moment.resolve_status == ResolveStatus.RESOLVED,
            Moment.created_at < func.current_date() - timedelta(days=60),
            func.length(lead) >= 15,
        )
        .order_by(func.md5(func.concat(Moment.id, func.current_date())), Moment.id)
        .offset(skip)
        .limit(1)
    ).first()
    if row is None:
        return ResurfaceNone()
    moment, title, metadata = row
    return ResurfaceFound(
        moment=FeedMoment(
            **MomentRead.model_validate(moment).model_dump(),
            video_title=title,
            video_metadata=metadata,
        )
    )


def get_for_user(db: Session, user_id: int, moment_id: int) -> Moment | None:
    return db.execute(
        select(Moment).where(Moment.user_id == user_id, Moment.id == moment_id)
    ).scalar_one_or_none()


def update(db: Session, moment: Moment, fields: dict) -> Moment:
    logger.debug(
        "Updating moment", extra={"moment_id": moment.id, "fields": sorted(fields)}
    )
    for name, value in fields.items():
        if name in MOMENT_TEXT_FIELDS and value != getattr(moment, name):
            moment.embedding = None
        setattr(moment, name, value)
    db.commit()
    db.refresh(moment)
    return moment


def delete(db: Session, moment: Moment) -> None:
    logger.debug("Deleting moment", extra={"moment_id": moment.id})
    db.delete(moment)
    db.commit()
