"""Text embeddings through OpenRouter, for meaning-based search."""

import base64
import binascii
import math
import struct

import requests

from src.config import settings

TIMEOUT_SECONDS = 20
BATCH_SIZE = 48
MAX_CHARS = 6000
# The model returns 4096 numbers, asked for as base64 little-endian float32
# because that is about a quarter the size of a JSON array; the first 1024 are
# kept. Search uses cosine distance, so the shortened vectors need no
# re-normalising.
DIMENSIONS = 1024
# pgvector stores float32; a larger component makes the database write fail.
FLOAT32_MAX = 3.4028234663852886e38
QUERY_PREFIX = (
    "Instruct: Given a question, retrieve transcript passages that answer it\nQuery: "
)
# Pinned so every vector comes from the same model build.
PROVIDER = {"order": ["Nebius", "DeepInfra"], "allow_fallbacks": False}


class EmbeddingError(Exception):
    pass


def _request(texts: list[str]) -> tuple[list[list[float]], int]:
    try:
        response = requests.post(
            f"{settings.openrouter_base_url}/embeddings",
            json={
                "model": settings.embedding_model,
                "input": texts,
                "provider": PROVIDER,
                "encoding_format": "base64",
            },
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "X-Title": "VidWiz",
            },
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise EmbeddingError(f"Embedding request failed: {type(exc).__name__}") from exc
    if not response.ok:
        raise EmbeddingError(f"Embedding API returned HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise EmbeddingError("Embedding API returned invalid JSON") from exc
    return _parse(payload, len(texts))


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    """A finite number that fits pgvector's float32 components."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        number = float(value)
    except OverflowError:
        return False
    return math.isfinite(number) and abs(number) <= FLOAT32_MAX


def _vector(value) -> list:
    """The kept components, from base64 float32 or, if the provider ignores
    the encoding, a JSON list of numbers."""
    if isinstance(value, list):
        if len(value) < DIMENSIONS:
            raise EmbeddingError("Embedding API returned a short vector")
        return value[:DIMENSIONS]
    if not isinstance(value, str):
        raise EmbeddingError("Embedding API returned a short vector")
    try:
        raw = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise EmbeddingError("Embedding API returned invalid base64") from exc
    if len(raw) % 4:
        raise EmbeddingError("Embedding API returned a partial float32 vector")
    if len(raw) < DIMENSIONS * 4:
        raise EmbeddingError("Embedding API returned a short vector")
    return list(struct.unpack(f"<{DIMENSIONS}f", raw[: DIMENSIONS * 4]))


def _parse(payload, count: int) -> tuple[list[list[float]], int]:
    """Check the whole response before returning any of it."""
    if not isinstance(payload, dict):
        raise EmbeddingError("Embedding API returned a non-object response")
    data = payload.get("data")
    if not isinstance(data, list) or len(data) != count:
        raise EmbeddingError("Embedding API returned the wrong number of vectors")
    by_index: dict[int, list[float]] = {}
    for item in data:
        if not isinstance(item, dict):
            raise EmbeddingError("Embedding API returned a non-object item")
        index = item.get("index")
        # Every input exactly once, so no vector lands on the wrong text.
        if not _is_int(index) or not 0 <= index < count or index in by_index:
            raise EmbeddingError("Embedding API returned invalid indices")
        vector = _vector(item.get("embedding"))
        if not all(_is_number(value) for value in vector):
            raise EmbeddingError("Embedding API returned an invalid vector component")
        by_index[index] = [float(value) for value in vector]
    usage = payload.get("usage")
    tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
    if not _is_int(tokens) or tokens < 0:
        raise EmbeddingError("Embedding API returned invalid token usage")
    return [by_index[index] for index in range(count)], tokens


def _embed(texts: list[str]) -> tuple[list[list[float]], int]:
    if not settings.openrouter_api_key:
        raise EmbeddingError("OPENROUTER_API_KEY is not configured")
    vectors: list[list[float]] = []
    tokens = 0
    for start in range(0, len(texts), BATCH_SIZE):
        batch = [text[:MAX_CHARS] for text in texts[start : start + BATCH_SIZE]]
        batch_vectors, batch_tokens = _request(batch)
        vectors.extend(batch_vectors)
        tokens += batch_tokens
    return vectors, tokens


def embed_documents(texts: list[str]) -> tuple[list[list[float]], int]:
    """Embed stored text; returns one vector per text and the tokens used."""
    return _embed(texts)


def embed_query(text: str) -> tuple[list[float], int]:
    """Embed a search question; returns its vector and the tokens used."""
    vectors, tokens = _embed([QUERY_PREFIX + text])
    return vectors[0], tokens
