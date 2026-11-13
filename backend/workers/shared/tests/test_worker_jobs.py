from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vidwiz_worker.jobs import PermanentError, receive_count, run_job  # noqa: E402


class Logger:
    def __init__(self):
        self.records = []

    def warning(self, message, **kwargs):
        self.records.append(("warning", message))

    def error(self, message, **kwargs):
        self.records.append(("error", message))


def _run(work, *, attempt, give_up_result=True):
    gave_up = []

    def give_up():
        gave_up.append(True)
        return give_up_result

    run_job(
        work,
        give_up,
        attempt=attempt,
        max_attempts=3,
        logger=Logger(),
        extra={"video_id": "v"},
    )
    return gave_up


def _raise(error):
    def work():
        raise error

    return work


def test_success_does_not_give_up():
    assert _run(lambda: None, attempt=1) == []


def test_failure_before_the_last_attempt_is_retried_by_sqs():
    with pytest.raises(RuntimeError, match="down"):
        _run(_raise(RuntimeError("down")), attempt=2)


def test_failure_on_the_last_attempt_is_recorded():
    assert _run(_raise(RuntimeError("down")), attempt=3) == [True]


def test_permanent_failure_is_recorded_at_once():
    assert _run(_raise(PermanentError("no transcript")), attempt=1) == [True]


def test_an_unrecorded_failure_goes_back_to_sqs():
    with pytest.raises(RuntimeError, match="record the job failure"):
        _run(_raise(PermanentError("no transcript")), attempt=1, give_up_result=False)


def test_receive_count_reads_the_sqs_attribute():
    record = SimpleNamespace(attributes=SimpleNamespace(ApproximateReceiveCount="3"))
    assert receive_count(record) == 3


def _run_reporting(work, *, attempt):
    from vidwiz_worker.jobs import run_job

    reports = []
    run_job(
        work,
        lambda: True,
        attempt=attempt,
        max_attempts=3,
        logger=Logger(),
        extra={},
        report=lambda reason, attempt, final: reports.append((reason, attempt, final)),
    )
    return reports


def test_failed_attempts_are_reported_with_the_provider_reason():
    from vidwiz_worker.jobs import ProviderError

    def work():
        raise ProviderError("provider_quota")

    reports = []
    with pytest.raises(ProviderError):
        from vidwiz_worker.jobs import run_job

        run_job(
            work,
            lambda: True,
            attempt=1,
            max_attempts=3,
            logger=Logger(),
            extra={},
            report=lambda *args: reports.append(args),
        )
    assert reports == [("provider_quota", 1, False)]
    assert _run_reporting(work, attempt=3) == [("provider_quota", 3, True)]


def test_invalid_output_is_reported_but_missing_transcript_is_not():
    from vidwiz_worker.jobs import InvalidOutputError

    def invalid():
        raise InvalidOutputError("bad")

    def missing():
        raise PermanentError("no transcript")

    assert _run_reporting(invalid, attempt=1) == [("invalid_output", 1, True)]
    assert _run_reporting(missing, attempt=1) == []


def test_a_failing_report_does_not_change_job_handling():
    from vidwiz_worker.jobs import ProviderError

    def work():
        raise ProviderError("provider_error")

    def report(*_args):
        raise RuntimeError("API down")

    gave_up = []
    run_job(
        work,
        lambda: gave_up.append(True) or True,
        attempt=3,
        max_attempts=3,
        logger=Logger(),
        extra={},
        report=report,
    )
    assert gave_up == [True]
