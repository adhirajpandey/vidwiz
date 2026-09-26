from fastapi import Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.config import settings
from src.exceptions import (
    BadRequestError,
    ForbiddenError,
    UnauthorizedError,
)
from src.internal import constants as internal_constants
from src.internal.schemas import TaskPollParams


admin_auth = HTTPBearer(
    scheme_name="AdminBearer",
    description="Administrative token for internal worker endpoints.",
    auto_error=False,
)


def require_admin_token(
    authorization: HTTPAuthorizationCredentials | None = Security(admin_auth),
) -> None:
    if not authorization:
        raise UnauthorizedError("Missing or invalid Authorization header")

    token = authorization.credentials
    if token != settings.internal_api_admin_token:
        raise ForbiddenError("Invalid admin token")


def get_task_poll_params(
    task_type: str = Query(..., alias="type"),
    timeout: int | None = Query(default=None, ge=1),
) -> TaskPollParams:
    if task_type not in internal_constants.TASK_TYPE_MAP:
        raise BadRequestError("Invalid task type")

    return TaskPollParams(
        task_type=internal_constants.TASK_TYPE_MAP[task_type],
        timeout=min(
            timeout or internal_constants.TASK_REQUEST_DEFAULT_TIMEOUT,
            internal_constants.TASK_REQUEST_MAX_TIMEOUT,
        ),
    )
