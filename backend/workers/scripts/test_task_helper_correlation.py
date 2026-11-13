from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import uuid

import pytest


SCRIPT = Path(__file__).with_name("task-helper.py")


def _load_task_helper():
    name = f"test_task_helper_{uuid.uuid4().hex}"
    spec = spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_task_helper_returns_task_correlation_in_result_and_header(monkeypatch):
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
    monkeypatch.setattr(helper, "fetch", lambda _details: {"video_id": "video-id"})
    monkeypatch.setattr(
        helper,
        "send_task_result",
        lambda task_id, data, correlation_id=None: (
            submitted.append((task_id, data, correlation_id)) or True
        ),
    )

    with pytest.raises(SystemExit):
        helper.run()

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
