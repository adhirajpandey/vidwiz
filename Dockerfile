FROM python:3.11-slim

WORKDIR /app
COPY ./server /app

RUN pip install --upgrade pip setuptools && \
    pip install -r requirements.txt

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--log-level=debug", "--access-logfile=-", "--error-logfile=-", "--capture-output", "app:app"]