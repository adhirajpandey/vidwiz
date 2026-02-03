import pytest
from pydantic import ValidationError

from src.videos.schemas import VideoIdPath, VideoListParams


def test_video_list_params_normalizes_query():
    params = VideoListParams.model_validate({"q": "  a "})
    assert params.q == ""

    params = VideoListParams.model_validate({"q": "  query "})
    assert params.q == "query"


def test_video_list_params_clamps_pagination():
    params = VideoListParams.model_validate({"page": 0, "per_page": 100})
    assert params.page == 1
    assert params.per_page == 50


def test_video_id_path_normalizes_url():
    path = VideoIdPath.model_validate({"video_id": "https://youtu.be/abc123DEF45"})
    assert path.video_id == "abc123DEF45"


def test_video_id_path_rejects_invalid():
    with pytest.raises(ValidationError):
        VideoIdPath.model_validate({"video_id": "bad"})
