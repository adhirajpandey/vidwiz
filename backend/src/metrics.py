from fastapi import Depends, FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from src.internal.dependencies import require_admin_token


_instrumentator = Instrumentator()


def init_metrics(app: FastAPI) -> None:
    _instrumentator.instrument(app)
    _instrumentator.expose(
        app,
        endpoint="/v2/internal/metrics",
        include_in_schema=False,
        dependencies=[Depends(require_admin_token)],
    )
