"""Jev decisions through OpenRouter: bounded choices and probabilities, no text."""

import logging
from concurrent.futures import ThreadPoolExecutor, wait

import requests

from src.config import settings

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 15
BATCH_SIZE = 12
MAX_WORKERS = 4
PASSAGE_MAX_CHARS = 1200


class JevError(Exception):
    pass


def decide(state: dict, questions: dict, timeout: float = TIMEOUT_SECONDS) -> dict:
    """Send one decisions request and return its raw answers."""
    if not settings.openrouter_api_key:
        raise JevError("OPENROUTER_API_KEY is not configured")
    try:
        response = requests.post(
            settings.jev_decisions_url,
            json={"model": settings.jev_model, "state": state, "questions": questions},
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "X-Title": "VidWiz",
            },
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise JevError(f"Jev request failed: {type(exc).__name__}") from exc
    if not response.ok:
        raise JevError(f"Jev returned HTTP {response.status_code}")
    payload = response.json()
    answers = payload.get("answers") or payload.get("decisions")
    if not isinstance(answers, dict):
        raise JevError("Jev returned no decisions")
    return answers


def _clip(text: str) -> str:
    text = " ".join(text.split())
    return text if len(text) <= PASSAGE_MAX_CHARS else text[:PASSAGE_MAX_CHARS] + " …"


def _relevance_batch(
    question: str, passages: list[str], timeout: float = TIMEOUT_SECONDS
) -> list[float]:
    keys = [f"p{index}" for index in range(len(passages))]
    answers = decide(
        {
            "question": question,
            "passages": {key: _clip(text) for key, text in zip(keys, passages)},
        },
        {
            key: {
                "type": "noul",
                "instructions": (
                    f"Does passage {key} contain information that helps answer "
                    "the question?"
                ),
            }
            for key in keys
        },
        timeout,
    )
    scores = []
    for key in keys:
        value = (answers.get(key) or {}).get("noul")
        if not isinstance(value, (int, float)) or not 0 <= value <= 1:
            raise JevError(f"Jev returned an invalid probability for {key}")
        scores.append(float(value))
    return scores


def relevance(
    question: str, passages: list[str], timeout: float = TIMEOUT_SECONDS
) -> list[float]:
    """Probability that each passage helps answer the question.

    Passages are scored in parallel batches, so each request stays small; Jev
    loses accuracy on long, mostly irrelevant state. Raises JevError when the
    scores are not all back within ``timeout`` seconds; requests still running
    then finish in the background.
    """
    batches = [
        passages[start : start + BATCH_SIZE]
        for start in range(0, len(passages), BATCH_SIZE)
    ]
    pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)
    try:
        futures = [
            pool.submit(_relevance_batch, question, batch, timeout) for batch in batches
        ]
        _, pending = wait(futures, timeout=timeout)
        if pending:
            raise JevError(f"Jev took longer than {timeout} seconds")
        return [score for future in futures for score in future.result()]
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
