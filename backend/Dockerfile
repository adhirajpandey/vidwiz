# Stage 1: Build frontend
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

# Install dependencies (using cache efficiently)
COPY frontend/package*.json ./
RUN npm install

# Copy frontend code and build
COPY frontend/ .
RUN npm run build


# Stage 2: Backend (Python)
FROM python:3.11-slim

WORKDIR /app

# Install Poetry
RUN pip install --upgrade pip setuptools && \
    pip install poetry

# Copy only dependency files first (for better cache usage)
COPY backend/pyproject.toml backend/poetry.lock /app/
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi

# Copy backend source
COPY backend/ /app/

# Copy built frontend (from stage 1) into backend/vidwiz/dist
COPY --from=frontend-builder /app/frontend/dist /app/vidwiz/dist

# Expose app port
EXPOSE 5000

# Run gunicorn
CMD ["poetry", "run", "gunicorn", "-w", "4", "--threads", "2", "--bind", "0.0.0.0:5000", "wsgi:app"]
