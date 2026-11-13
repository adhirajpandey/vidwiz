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


class InvalidOutputError(PermanentError):
    """The model kept returning output that fails validation."""


class ProviderError(RuntimeError):
    """The model provider rejected or failed the request; kind names how."""

    def __init__(self, kind: str):
        super().__init__(f"Model request failed ({kind})")
        self.kind = kind


def failure_kind(error: Exception) -> str:
    """Map a failed attempt to the API's bounded attempt failure reasons."""
    if isinstance(error, ProviderError):
        return error.kind
    if isinstance(error, InvalidOutputError):
        return "invalid_output"
    if isinstance(error, TimeoutError) or "Timeout" in type(error).__name__:
        return "timeout"
    return "worker_error"


def run_job(
    work: Callable[[], None],
    give_up: Callable[[], bool],
    *,
    attempt: int,
    max_attempts: int,
    logger: Any,
    extra: dict,
    report: Callable[[str, int, bool], Any] | None = None,
) -> None:
    """Run one job; on failure, retry through SQS or record the failure.

    report, when given, receives (reason, attempt, final) for each failed
    attempt so the API can count why work is failing before it gives up.
    """

    def report_failure(error: Exception, final: bool) -> None:
        if report is None:
            return
        try:
            report(failure_kind(error), attempt, final)
        except Exception as report_error:  # noqa: BLE001
            # Metrics must never change how the job itself is handled.
            logger.warning(
                "Could not report the failed attempt",
                extra={**extra, "error": str(report_error)},
            )

    try:
        work()
        return
    except PermanentError as error:
        logger.error("Job failed for good", extra={**extra, "reason": str(error)})
        if isinstance(error, InvalidOutputError):
            report_failure(error, True)
    except Exception as error:
        if attempt < max_attempts:
            logger.warning(
                "Job failed; SQS retries it",
                extra={**extra, "attempt": attempt, "error": str(error)},
            )
            report_failure(error, False)
            raise
        logger.error(
            "Job failed on its last attempt",
            extra={**extra, "attempt": attempt, "error": str(error)},
        )
        report_failure(error, True)
    if not give_up():
        raise RuntimeError("Could not record the job failure")


def receive_count(record: Any) -> int:
    """How many times SQS has delivered this record, starting at 1."""
    return int(record.attributes.ApproximateReceiveCount)
