from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import uuid

import pytest


def _load_module(script_name: str):
    script_path = (
        Path(__file__).resolve().parents[2] / "workers" / "scripts" / script_name
    )
    module_name = f"test_{script_name.replace('-', '_').replace('.py', '')}_{uuid.uuid4().hex}"
    spec = spec_from_file_location(module_name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("script_name", "helper_class_name"),
    [
        ("transcript-helper.py", "TranscriptHelper"),
        ("metadata-helper.py", "MetadataHelper"),
    ],
)
def test_helper_uses_internal_api_url_env(script_name, helper_class_name, monkeypatch):
    module = _load_module(script_name)
    monkeypatch.setenv("INTERNAL_API_URL", "http://internal.example:5000")

    resolved = module.resolve_api_url(None)
    helper = getattr(module, helper_class_name)("token", 30, resolved)

    assert resolved == "http://internal.example:5000"
    assert helper.tasks_url == "http://internal.example:5000/v2/internal/tasks"


@pytest.mark.parametrize(
    ("script_name", "helper_class_name"),
    [
        ("transcript-helper.py", "TranscriptHelper"),
        ("metadata-helper.py", "MetadataHelper"),
    ],
)
def test_helper_prefers_cli_api_url_over_env(
    script_name, helper_class_name, monkeypatch
):
    module = _load_module(script_name)
    monkeypatch.setenv("INTERNAL_API_URL", "http://internal.example:5000")

    resolved = module.resolve_api_url("http://cli.example:5000/")
    helper = getattr(module, helper_class_name)("token", 30, resolved)

    assert resolved == "http://cli.example:5000/"
    assert helper.tasks_url == "http://cli.example:5000/v2/internal/tasks"


@pytest.mark.parametrize(
    "script_name",
    ["transcript-helper.py", "metadata-helper.py"],
)
def test_helper_exits_when_api_url_missing(script_name, monkeypatch):
    module = _load_module(script_name)
    monkeypatch.delenv("INTERNAL_API_URL", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        module.resolve_api_url(None)

    assert exc_info.value.code == 1


@pytest.mark.parametrize(
    ("script_name", "helper_class_name"),
    [
        ("transcript-helper.py", "TranscriptHelper"),
        ("metadata-helper.py", "MetadataHelper"),
    ],
)
def test_helper_task_result_url_uses_normalized_base(
    script_name, helper_class_name, monkeypatch
):
    module = _load_module(script_name)
    helper = getattr(module, helper_class_name)("token", 30, "http://api.example/")

    captured = {}

    class DummyResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "ok"}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return DummyResponse()

    monkeypatch.setattr(module.requests, "post", fake_post)

    if helper_class_name == "TranscriptHelper":
        helper.send_task_result(7, "abc123DEF45", transcript=[{"text": "hi"}])
    else:
        helper.send_task_result(7, "abc123DEF45", metadata={"title": "hi"})

    assert captured["url"] == "http://api.example/v2/internal/tasks/7/result"
    assert captured["kwargs"]["headers"] == {"Authorization": "Bearer token"}
