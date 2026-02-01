from vidwiz.shared.models import Note, Video
from vidwiz.shared.schemas import SearchResponse, VideoSearchItem


def search_videos_for_user(user_id: int, query: str, page: int, per_page: int):
    base_query = (
        Video.query.join(Note, Video.video_id == Note.video_id)
        .filter(Note.user_id == user_id)
        .group_by(Video.id)
        .order_by(Video.created_at.desc())
    )

    if query:
        base_query = base_query.filter(Video.title.ilike(f"%{query}%"))

    total = base_query.count()

    if total == 0:
        return SearchResponse(
            videos=[],
            total=0,
            page=page,
            per_page=per_page,
            total_pages=0,
        )

    total_pages = (total + per_page - 1) // per_page

    videos = base_query.offset((page - 1) * per_page).limit(per_page).all()

    videos_data = [
        VideoSearchItem(
            video_id=video.video_id,
            video_title=video.title,
            metadata=video.video_metadata,
        )
        for video in videos
    ]

    return SearchResponse(
        videos=videos_data,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )
