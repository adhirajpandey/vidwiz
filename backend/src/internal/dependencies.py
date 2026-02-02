from fastapi import Header, Query

from src.config import settings
from src.exceptions import BadRequestError, ForbiddenError, InternalServerError, UnauthorizedError
from src.internal import constants as internal_constants
from src.internal.schemas import TaskPollParams


def require_admin_token(
    authorization: str | None = Header(default=None),
) -> None:
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing or invalid Authorization header")

    token = authorization.split(" ", 1)[1]
    if not settings.admin_token:
        raise InternalServerError("Admin token is not configured")

    if token != settings.admin_token:
        raise ForbiddenError("Invalid admin token")


def get_task_poll_params(
    task_type: str = Query(..., alias="type"),
    timeout: int | None = Query(default=None, ge=1),
) -> TaskPollParams:
    if task_type not in internal_constants.TASK_TYPE_MAP:
        raise BadRequestError("Invalid task type")

    resolved_type = internal_constants.TASK_TYPE_MAP[task_type]

    if task_type == "transcript":
        default_timeout = internal_constants.TRANSCRIPT_TASK_REQUEST_DEFAULT_TIMEOUT
        max_timeout = internal_constants.TRANSCRIPT_TASK_REQUEST_MAX_TIMEOUT
        poll_interval = internal_constants.TRANSCRIPT_POLL_INTERVAL
        max_retries = internal_constants.FETCH_TRANSCRIPT_MAX_RETRIES
        in_progress_timeout = internal_constants.FETCH_TRANSCRIPT_IN_PROGRESS_TIMEOUT
    else:
        default_timeout = internal_constants.METADATA_TASK_REQUEST_DEFAULT_TIMEOUT
        max_timeout = internal_constants.METADATA_TASK_REQUEST_MAX_TIMEOUT
        poll_interval = internal_constants.METADATA_POLL_INTERVAL
        max_retries = internal_constants.FETCH_METADATA_MAX_RETRIES
        in_progress_timeout = internal_constants.FETCH_METADATA_IN_PROGRESS_TIMEOUT

    selected_timeout = default_timeout if timeout is None else min(timeout, max_timeout)

    return TaskPollParams(
        task_type=resolved_type,
        timeout=selected_timeout,
        poll_interval=poll_interval,
        max_retries=max_retries,
        in_progress_timeout=in_progress_timeout,
    )
