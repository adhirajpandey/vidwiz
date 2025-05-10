FROM python:3.11-alpine3.15

WORKDIR /app

COPY ./server /app

RUN apk add --no-cache gcc musl-dev postgresql-dev

RUN pip install --upgrade pip setuptools
RUN pip install -r requirements.txt

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--log-level=debug", "--access-logfile=-", "--error-logfile=-", "--capture-output", "app:app"]