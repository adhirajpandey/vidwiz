FROM python:3.11-slim

WORKDIR /app
COPY . /app

# Install Poetry
RUN pip install --upgrade pip setuptools && \
    pip install poetry

# Install dependencies using Poetry
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi

CMD ["poetry", "run", "gunicorn", "-w", "4", "--threads", "2", "--bind", "0.0.0.0:5000", "--log-level=debug", "--access-logfile=-", "--error-logfile=-", "--capture-output", "wsgi:app"]