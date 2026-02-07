import pytest

from src.auth.schemas import ViewerContext
from src.exceptions import BadRequestError, NotFoundError
from src.notes.models import Note
from src.videos import dependencies as videos_dependencies
from src.videos.models import Video


def test_get_video_list_params_rejects_invalid_sort():
    with pytest.raises(BadRequestError):
        videos_dependencies.get_video_list_params(sort="invalid")


def test_get_video_list_params_accepts_valid_sort():
    params = videos_dependencies.get_video_list_params(
        q="",
        page=1,
        per_page=10,
        sort="title_desc",
    )
    assert params.sort == "title_desc"


def test_get_user_video_or_404(db_session):
    video = Video(video_id="dep1234567A", title="Dep Video")
    db_session.add(video)
    db_session.commit()

    path = videos_dependencies.VideoIdPath.model_validate({"video_id": "dep1234567A"})
    result = videos_dependencies.get_user_video_or_404(
        path=path, db=db_session, user_id=1
    )
    assert result.video_id == "dep1234567A"

    missing_path = videos_dependencies.VideoIdPath.model_validate(
        {"video_id": "mis1234567A"}
    )
    with pytest.raises(NotFoundError):
        videos_dependencies.get_user_video_or_404(
            path=missing_path, db=db_session, user_id=1
        )


def test_get_stream_video_or_404_user_scoped(db_session):
    video = Video(video_id="stream12345", title="Stream")
    db_session.add(video)
    db_session.commit()

    note = Note(video_id=video.video_id, timestamp="00:01", text="note", user_id=5)
    db_session.add(note)
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
