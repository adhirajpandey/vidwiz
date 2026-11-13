from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import uuid
import logging

import pytest


SCRIPT = Path(__file__).with_name("task-helper.py")


def _load_task_helper():
    name = f"test_task_helper_{uuid.uuid4().hex}"
    spec = spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("fail", [False, True])
def test_task_helper_returns_task_correlation_in_result_and_header(
    monkeypatch, caplog, fail
):
    caplog.set_level(logging.INFO, logger="vidwiz.task_helper")
    module = _load_task_helper()
    helper = module.TaskHelper("metadata", "token", 1, "https://api.example")
    responses = iter(
        [
            {
                "task_id": 7,
                "task_details": {
                    "video_id": "video-id",
                    "correlation_id": "trace:abc-123",
                },
            }
        ]
    )

    def get_task():
        try:
            return next(responses)
        except StopIteration:
            raise SystemExit

    submitted = []
    monkeypatch.setattr(helper, "get_task", get_task)

    def fetch(_details):
        if fail:
            raise ValueError("test failure")
        return {"video_id": "video-id"}

    monkeypatch.setattr(helper, "fetch", fetch)
    monkeypatch.setattr(
        helper,
        "send_task_result",
        lambda task_id, data, correlation_id=None: (
            submitted.append((task_id, data, correlation_id)) or True
        ),
    )

    with pytest.raises(SystemExit):
        helper.run()

    lifecycle = [
        r.getMessage()
        for r in caplog.records
        if r.name == "vidwiz.task_helper"
        and ("task_id=" in r.getMessage() or "Failed to process" in r.getMessage())
    ]
    assert len(lifecycle) >= 2
    assert all("trace:abc-123" in message for message in lifecycle)
    if fail:
        assert submitted == [
            (
                7,
                {
                    "video_id": "video-id",
                    "success": False,
                    "error_message": "test failure",
                    "error_kind": "worker_error",
                },
                "trace:abc-123",
            )
        ]
        return
    assert submitted == [
        (
            7,
            {
                "video_id": "video-id",
                "success": True,
                "correlation_id": "trace:abc-123",
            },
            "trace:abc-123",
        )
    ]


@pytest.mark.parametrize("fail", [False, True])
def test_callback_logs_and_header_include_correlation(monkeypatch, caplog, fail):
    module = _load_task_helper()
    helper = module.TaskHelper("metadata", "token", 1, "https://api.example")
    caplog.set_level(logging.INFO, logger="vidwiz.task_helper")

    def post(url, **kwargs):
        assert kwargs["headers"]["X-Correlation-ID"] == "trace:abc-123"
        if fail:
            raise module.requests.RequestException("test failure")

        class Response:
            def raise_for_status(self):
                pass

            def json(self):
                return {"status": "accepted"}

        return Response()

    monkeypatch.setattr(module.requests, "post", post)
    assert helper.send_task_result(7, {"success": True}, "trace:abc-123") is not fail
    messages = [
        r.getMessage() for r in caplog.records if r.name == "vidwiz.task_helper"
    ]
    assert len(messages) == 2
    assert all("trace:abc-123" in message for message in messages)


def test_error_kind_names_the_broken_dependency():
    import requests

    module = _load_task_helper()

    class IpBlocked(Exception):
        pass

    class NoTranscriptFound(Exception):
        pass

    assert module.error_kind(IpBlocked("vid")) == "youtube_blocked"
    assert (
        module.error_kind(Exception("ERROR: Sign in to confirm you're not a bot"))
        == "youtube_blocked"
    )
    assert module.error_kind(requests.exceptions.ProxyError("x")) == "proxy_error"
    assert module.error_kind(requests.exceptions.ReadTimeout("x")) == "timeout"
    assert module.error_kind(LookupError("No YouTube results")) == "not_found"
    assert module.error_kind(NoTranscriptFound("x")) == "not_found"
    assert module.error_kind(ValueError("other")) == "worker_error"
