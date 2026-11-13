"""Text embeddings through OpenRouter, for meaning-based search."""

import requests

from src.config import settings

TIMEOUT_SECONDS = 20
BATCH_SIZE = 48
MAX_CHARS = 6000
# The model returns 4096 numbers; the first 1024 are kept. Search uses cosine
# distance, so the shortened vectors need no re-normalising.
DIMENSIONS = 1024
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
    payload = response.json()
    data = payload.get("data")
    if not isinstance(data, list) or len(data) != len(texts):
        raise EmbeddingError("Embedding API returned the wrong number of vectors")
    vectors = []
    for item in sorted(data, key=lambda item: item.get("index", 0)):
        vector = item.get("embedding")
        if not isinstance(vector, list) or len(vector) < DIMENSIONS:
            raise EmbeddingError("Embedding API returned a short vector")
        vectors.append(vector[:DIMENSIONS])
    tokens = (payload.get("usage") or {}).get("total_tokens") or 0
    return vectors, int(tokens)


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
