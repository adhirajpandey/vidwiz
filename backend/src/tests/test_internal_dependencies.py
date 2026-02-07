import pytest

from src.internal import dependencies as internal_dependencies
from src.internal import constants as internal_constants
from src.exceptions import (
    BadRequestError,
    ForbiddenError,
    InternalServerError,
    UnauthorizedError,
)
from src.config import settings


def test_require_admin_token_errors(monkeypatch):
    with pytest.raises(UnauthorizedError):
        internal_dependencies.require_admin_token(None)

    monkeypatch.setattr(settings, "admin_token", None, raising=False)
    with pytest.raises(InternalServerError):
        internal_dependencies.require_admin_token("Bearer token")

    monkeypatch.setattr(settings, "admin_token", "expected", raising=False)
    with pytest.raises(ForbiddenError):
        internal_dependencies.require_admin_token("Bearer wrong")


def test_require_admin_token_success(monkeypatch):
    monkeypatch.setattr(settings, "admin_token", "expected", raising=False)
    internal_dependencies.require_admin_token("Bearer expected")


def test_get_task_poll_params_validation():
    with pytest.raises(BadRequestError):
        internal_dependencies.get_task_poll_params(task_type="bad")

    params = internal_dependencies.get_task_poll_params(
        task_type="transcript", timeout=999
    )
    assert params.task_type == internal_constants.FETCH_TRANSCRIPT_TASK_TYPE
    assert params.timeout == internal_constants.TRANSCRIPT_TASK_REQUEST_MAX_TIMEOUT

    params = internal_dependencies.get_task_poll_params(task_type="metadata", timeout=1)
    assert params.task_type == internal_constants.FETCH_METADATA_TASK_TYPE
