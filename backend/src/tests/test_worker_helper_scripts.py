from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import uuid

import pytest


def _load_module(script_name: str):
    script_path = (
        Path(__file__).resolve().parents[2] / "workers" / "scripts" / script_name
    )
    module_name = (
        f"test_{script_name.replace('-', '_').replace('.py', '')}_{uuid.uuid4().hex}"
    )
    spec = spec_from_file_location(module_name, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_helper():
    return _load_module("task-helper.py")


def test_helper_uses_canonical_internal_api_url_env(monkeypatch):
    module = _load_helper()
    monkeypatch.setenv("VIDWIZ_INTERNAL_API_BASE_URL", "http://internal.example:5000")

    resolved = module.resolve_api_url(None)
    helper = module.TaskHelper("metadata", "token", 30, resolved)

    assert resolved == "http://internal.example:5000"
    assert helper.tasks_url == "http://internal.example:5000/v2/internal/tasks"


def test_helper_prefers_cli_api_url_over_env(monkeypatch):
    module = _load_helper()
    monkeypatch.setenv("VIDWIZ_INTERNAL_API_BASE_URL", "http://internal.example:5000")

    resolved = module.resolve_api_url("http://cli.example:5000/")
    helper = module.TaskHelper("transcript", "token", 30, resolved)

    assert resolved == "http://cli.example:5000/"
    assert helper.tasks_url == "http://cli.example:5000/v2/internal/tasks"


def test_helper_exits_when_api_url_missing(monkeypatch):
    module = _load_helper()
    monkeypatch.delenv("VIDWIZ_INTERNAL_API_BASE_URL", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        module.resolve_api_url(None)

    assert exc_info.value.code == 1


@pytest.mark.parametrize(
    ("task_type", "fetcher", "value", "field"),
    [
        ("transcript", "fetch_transcript", [{"text": "hi"}], "transcript"),
        ("metadata", "fetch_metadata", {"title": "hi"}, "metadata"),
    ],
)
def test_video_tasks_build_result_payloads(
    task_type, fetcher, value, field, monkeypatch
):
    module = _load_helper()
    monkeypatch.setattr(module, fetcher, lambda video_id: value)

    payload = module.TASKS[task_type]({"video_id": "abc123DEF45"})

    assert payload == {"video_id": "abc123DEF45", field: value}


def test_helper_submits_result_payload(monkeypatch):
    module = _load_helper()
    helper = module.TaskHelper("metadata", "token", 30, "http://api.example/")
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
    helper.send_task_result(7, {"video_id": "abc123DEF45", "success": True})

    assert captured["url"] == "http://api.example/v2/internal/tasks/7/result"
    assert captured["kwargs"]["headers"] == {"Authorization": "Bearer token"}
    assert captured["kwargs"]["json"] == {"video_id": "abc123DEF45", "success": True}


def _fake_search(monkeypatch, module, entries):
    class FakeYdl:
        def __init__(self, options):
            assert options["extract_flat"] is True

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def extract_info(self, query, download):
            assert query.startswith("ytsearch5:")
            return {"entries": entries}

    monkeypatch.setattr(module.yt_dlp, "YoutubeDL", FakeYdl)


def test_resolve_title_prefers_single_matching_channel(monkeypatch):
    module = _load_helper()
    _fake_search(
        monkeypatch,
        module,
        [
            {"id": "aaaaaaaaaaa", "title": "Deep Focus", "channel": "Someone"},
            {"id": "bbbbbbbbbbb", "title": "Deep focus …", "channel": "Odysseas"},
        ],
    )

    payload = module.TASKS["resolve_title"](
        {"title": "Deep Focus", "channel": "odysseas"}
    )

    assert payload == {"resolved": {"video_id": "bbbbbbbbbbb", "title": "Deep focus …"}}


def test_resolve_title_ignores_punctuation_in_titles(monkeypatch):
    module = _load_helper()
    _fake_search(
        monkeypatch,
        module,
        [
            {
                "id": "aaaaaaaaaaa",
                "title": "Steve Jobs' 2005 Address",
                "channel": "Stanford",
            },
            {
                "id": "bbbbbbbbbbb",
                "title": "Steve Jobs' 2005 Address (with intro)",
                "channel": "Stanford",
            },
        ],
    )
    payload = module.resolve_title("Steve Jobs 2005 address", "Stanford")
    assert payload["resolved"]["video_id"] == "aaaaaaaaaaa"


def test_resolve_title_uses_unique_exact_title(monkeypatch):
    module = _load_helper()
    _fake_search(
        monkeypatch,
        module,
        [
            {"id": "aaaaaaaaaaa", "title": "Something else"},
            {"id": "bbbbbbbbbbb", "title": "Deep Focus"},
        ],
    )
    assert module.resolve_title("deep focus")["resolved"]["video_id"] == "bbbbbbbbbbb"


@pytest.mark.parametrize(
    ("confidence", "expected"),
    [(0.9, "resolved"), (0.4, "candidates")],
)
def test_resolve_title_asks_jev_when_ambiguous(monkeypatch, confidence, expected):
    module = _load_helper()
    entries = [
        {"id": "aaaaaaaaaaa", "title": "Focus part 1", "channel": "A"},
        {"id": "bbbbbbbbbbb", "title": "Focus part 2", "channel": "B"},
    ]
    _fake_search(monkeypatch, module, entries)
    calls = []

    def fake_choose(title, channel, candidates):
        calls.append((title, channel, [c["video_id"] for c in candidates]))
        return "bbbbbbbbbbb", confidence

    monkeypatch.setattr(module, "jev_choose", fake_choose)

    payload = module.resolve_title("Focus", None)

    assert calls == [("Focus", None, ["aaaaaaaaaaa", "bbbbbbbbbbb"])]
    assert expected in payload
    if expected == "resolved":
        assert payload["resolved"]["video_id"] == "bbbbbbbbbbb"
    else:
        assert [c["video_id"] for c in payload["candidates"]] == [
            "aaaaaaaaaaa",
            "bbbbbbbbbbb",
        ]


def test_resolve_title_offers_candidates_when_jev_fails(monkeypatch):
    module = _load_helper()
    _fake_search(
        monkeypatch,
        module,
        [{"id": "aaaaaaaaaaa", "title": "One"}, {"id": "bbbbbbbbbbb", "title": "Two"}],
    )
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    payload = module.resolve_title("Neither")

    assert len(payload["candidates"]) == 2


def test_jev_choose_parses_choice(monkeypatch):
    module = _load_helper()
    monkeypatch.setenv("OPENROUTER_API_KEY", "key")
    sent = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"answers": {"video": {"choice": "v1", "confidence": 0.8}}}

    def fake_post(url, json, headers, timeout):
        sent.update(json)
        return Response()

    monkeypatch.setattr(module.requests, "post", fake_post)

    result = module.jev_choose(
        "Focus",
        "B",
        [
            {"video_id": "aaaaaaaaaaa", "title": "Focus 1", "channel": "A"},
            {"video_id": "bbbbbbbbbbb", "title": "Focus 2", "channel": "B"},
        ],
    )

    assert result == ("bbbbbbbbbbb", 0.8)
    assert sent["questions"]["video"]["criteria"]["v1"] == "Focus 2 (channel: B)"


def test_resolve_title_raises_without_results(monkeypatch):
    module = _load_helper()
    _fake_search(monkeypatch, module, [])
    with pytest.raises(LookupError):
        module.resolve_title("Deep Focus")


def test_transcript_fetch_renames_start_to_offset(monkeypatch):
    module = _load_helper()

    class FakeApi:
        def fetch(self, video_id, languages):
            assert languages == ["en", "hi"]
            return self

        def to_raw_data(self):
            return [{"text": "hi", "start": 1.5, "duration": 2}]

    monkeypatch.setattr(module, "YouTubeTranscriptApi", FakeApi)

    assert module.fetch_transcript("abc123DEF45") == [
        {"text": "hi", "duration": 2, "offset": 1.5}
    ]


def test_helper_backs_off_when_polling_fails(monkeypatch):
    module = _load_helper()
    helper = module.TaskHelper("metadata", "token", 30, "http://api.example")
    sleeps = []

    def fail_get(*_args, **_kwargs):
        raise module.requests.ConnectionError("refused")

    monkeypatch.setattr(module.requests, "get", fail_get)
    monkeypatch.setattr(module.time, "sleep", sleeps.append)

    assert helper.get_task() is None
    assert sleeps == [module.POLL_ERROR_BACKOFF_SECONDS]
