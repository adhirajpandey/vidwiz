# syntax=docker/dockerfile:1

FROM ghcr.io/astral-sh/uv:0.8.22 AS uv

FROM python:3.13-slim

WORKDIR /app

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy

# curl is used by the Docker Compose health check.
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /bin/

# Install the dependency layer first for better caching.
COPY backend/pyproject.toml backend/uv.lock /app/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# Copy application source after dependencies.
COPY backend/ /app/

# Refresh the locked runtime environment after copying source.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable

RUN groupadd --system --gid 10001 app && \
    useradd --system --uid 10001 --gid app --home-dir /app app && \
    chown -R app:app /app

USER app

EXPOSE 5000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5000"]
