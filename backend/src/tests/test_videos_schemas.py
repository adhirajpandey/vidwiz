import pytest
from pydantic import ValidationError

from src.videos.schemas import VideoIdPath


def test_video_id_path_normalizes_url():
    path = VideoIdPath.model_validate({"video_id": "https://youtu.be/abc123DEF45"})
    assert path.video_id == "abc123DEF45"


def test_video_id_path_rejects_invalid():
    with pytest.raises(ValidationError):
        VideoIdPath.model_validate({"video_id": "bad"})
