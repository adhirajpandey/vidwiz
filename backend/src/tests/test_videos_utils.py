import pytest

from src.videos.utils import normalize_youtube_video_id


def test_normalize_youtube_video_id_accepts_raw_id():
    assert normalize_youtube_video_id("abc123DEF45") == "abc123DEF45"


def test_normalize_youtube_video_id_trims_input():
    assert normalize_youtube_video_id("  abc123DEF45  ") == "abc123DEF45"


def test_normalize_youtube_video_id_accepts_youtu_be():
    assert (
        normalize_youtube_video_id("https://youtu.be/abc123DEF45")
        == "abc123DEF45"
    )


def test_normalize_youtube_video_id_accepts_watch_url():
    assert (
        normalize_youtube_video_id("https://www.youtube.com/watch?v=abc123DEF45")
        == "abc123DEF45"
    )


def test_normalize_youtube_video_id_accepts_shorts_url():
    assert (
        normalize_youtube_video_id("https://youtube.com/shorts/abc123DEF45")
        == "abc123DEF45"
    )


def test_normalize_youtube_video_id_accepts_embed_url():
    assert (
        normalize_youtube_video_id("https://youtube.com/embed/abc123DEF45")
        == "abc123DEF45"
    )


def test_normalize_youtube_video_id_accepts_live_url():
    assert (
        normalize_youtube_video_id("https://youtube.com/live/abc123DEF45")
        == "abc123DEF45"
    )


def test_normalize_youtube_video_id_rejects_playlist():
    with pytest.raises(ValueError):
        normalize_youtube_video_id("https://youtube.com/watch?v=abc123DEF45&list=xyz")


def test_normalize_youtube_video_id_rejects_invalid_id():
    with pytest.raises(ValueError):
        normalize_youtube_video_id("not-a-video-id")
