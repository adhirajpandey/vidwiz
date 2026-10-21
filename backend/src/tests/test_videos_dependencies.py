import pytest

from src.auth.schemas import ViewerContext
from src.exceptions import NotFoundError
from src.videos import dependencies as videos_dependencies
from src.videos.models import Video


def test_get_stream_video_or_404_allows_authenticated_without_notes(db_session):
    video = Video(video_id="stream12345", title="Stream")
    db_session.add(video)
    db_session.commit()

    path = videos_dependencies.VideoIdPath.model_validate({"video_id": "stream12345"})
    viewer = ViewerContext(user_id=5)
    result = videos_dependencies.get_stream_video_or_404(
        path=path,
        db=db_session,
        viewer=viewer,
    )
    assert result.video_id == "stream12345"


def test_get_stream_video_or_404_guest_allows_public(db_session):
    video = Video(video_id="guest123456", title="Guest")
    db_session.add(video)
    db_session.commit()

    path = videos_dependencies.VideoIdPath.model_validate({"video_id": "guest123456"})
    viewer = ViewerContext(guest_session_id="guest-1")
    result = videos_dependencies.get_stream_video_or_404(
        path=path,
        db=db_session,
        viewer=viewer,
    )
    assert result.video_id == "guest123456"


def test_get_stream_video_or_404_missing_raises(db_session):
    path = videos_dependencies.VideoIdPath.model_validate({"video_id": "missing1234"})
    viewer = ViewerContext(user_id=2)
    with pytest.raises(NotFoundError):
        videos_dependencies.get_stream_video_or_404(
            path=path,
            db=db_session,
            viewer=viewer,
        )
