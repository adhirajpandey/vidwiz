"""Retry rules shared by the queue workers.

A job either succeeds, fails for good, or fails for now. SQS delivers a job
again after a failure for now, up to max_attempts times. A worker records the
failure itself when retrying cannot help or on the last attempt, so the API's
state never stays queued; only a failure it cannot record goes to the
dead-letter queue.
"""

from collections.abc import Callable
from typing import Any


class PermanentError(Exception):
    """Retrying cannot help, for example a missing transcript."""


def run_job(
    work: Callable[[], None],
    give_up: Callable[[], bool],
    *,
    attempt: int,
    max_attempts: int,
    logger: Any,
    extra: dict,
) -> None:
    """Run one job; on failure, retry through SQS or record the failure."""
    try:
        work()
        return
    except PermanentError as error:
        logger.error("Job failed for good", extra={**extra, "reason": str(error)})
    except Exception as error:
        if attempt < max_attempts:
            logger.warning(
                "Job failed; SQS retries it",
                extra={**extra, "attempt": attempt, "error": str(error)},
            )
            raise
        logger.error(
            "Job failed on its last attempt",
            extra={**extra, "attempt": attempt, "error": str(error)},
        )
    if not give_up():
        raise RuntimeError("Could not record the job failure")


def receive_count(record: Any) -> int:
    """How many times SQS has delivered this record, starting at 1."""
    return int(record.attributes.ApproximateReceiveCount)
