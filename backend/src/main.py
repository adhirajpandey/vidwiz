from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from src.auth.router import router as auth_router
from src.config import settings
from src.conversations.router import router as conversations_router
from src.exceptions import APIError, ErrorCode, HTTP_STATUS_CODE_MAP, RateLimitError
from src.internal.router import router as internal_router
from src.models import ErrorDetail, ErrorPayload, ErrorResponse
from src.notes.router import router as notes_router
from src.shared.ratelimit import limiter
from src.videos.router import router as videos_router


SHOW_DOCS_ENVIRONMENT = ("local", "staging")


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def handle_api_error(_: Request, exc: APIError) -> JSONResponse:
        response = exc.to_response()
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(mode="json"),
        )

    @app.exception_handler(RateLimitExceeded)
    async def handle_rate_limit(_: Request, exc: RateLimitExceeded) -> JSONResponse:
        retry_after = getattr(exc, "retry_after", None)
        details = None
        headers = None
        if retry_after is not None:
            reset_seconds = max(0, int(retry_after))
            details = {"reset_in_seconds": reset_seconds}
            headers = {"Retry-After": str(reset_seconds)}

        error = RateLimitError(details=details)
        return JSONResponse(
            status_code=error.status_code,
            content=error.to_response().model_dump(mode="json"),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            ErrorDetail(
                field=".".join(str(loc) for loc in error["loc"]),
                message=error["msg"],
                type=error.get("type"),
            )
            for error in exc.errors()
        ]
        response = ErrorResponse(
            error=ErrorPayload(
                code=ErrorCode.VALIDATION_ERROR,
                message="Request validation failed",
                details=details,
            )
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=response.model_dump(mode="json"),
        )

    @app.exception_handler(HTTPException)
    async def handle_http_exception(_: Request, exc: HTTPException) -> JSONResponse:
        code = HTTP_STATUS_CODE_MAP.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        response = ErrorResponse(
            error=ErrorPayload(
                code=code,
                message=str(exc.detail),
            )
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=response.model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def handle_unhandled(_: Request, exc: Exception) -> JSONResponse:
        response = ErrorResponse(
            error=ErrorPayload(
                code=ErrorCode.INTERNAL_ERROR,
                message="Internal Server Error",
            )
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=response.model_dump(mode="json"),
        )


def create_app() -> FastAPI:
    app_configs = {"title": "VidWiz API"}
    if settings.environment not in SHOW_DOCS_ENVIRONMENT:
        app_configs["openapi_url"] = None

    app = FastAPI(**app_configs)
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_referrer_policy(request: Request, call_next):
        response = await call_next(request)
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    app.include_router(videos_router)
    app.include_router(auth_router)
    app.include_router(notes_router)
    app.include_router(conversations_router)
    app.include_router(internal_router)

    register_exception_handlers(app)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=5000, reload=False)
