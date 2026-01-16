"""
Sync video metadata from YouTube for videos missing metadata in the database.

Usage: python sync-metadata.py
"""

import os
import sys

import yt_dlp

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from vidwiz.app import create_app
from vidwiz.shared.models import Video, db


def fetch_youtube_metadata(video_id: str) -> dict | None:
    """Fetch video metadata from YouTube using yt-dlp."""
    opts = {"quiet": True, "no_warnings": True}
    url = f"https://www.youtube.com/watch?v={video_id}"

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return {
            "id": info.get("id"),
            "title": info.get("title"),
            "uploader": info.get("uploader"),
            "upload_date": info.get("upload_date"),
            "duration": info.get("duration"),
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "channel_url": info.get("channel_url"),
            "description": info.get("description"),
            "thumbnail": info.get("thumbnail"),
        }
    except Exception as e:
        print(f"  ✗ Failed to fetch: {e}")
        return None


def sync_metadata():
    """Main sync function."""
    app = create_app()

    with app.app_context():
        # Get videos without metadata
        videos = Video.query.filter(Video.video_metadata.is_(None)).all()

        if not videos:
            print("No videos missing metadata.")
            return

        print(f"Found {len(videos)} videos without metadata\n")

        success, failed = 0, 0

        for video in videos:
            print(f"[{success + failed + 1}/{len(videos)}] {video.video_id}...", end=" ")

            metadata = fetch_youtube_metadata(video.video_id)

            if metadata:
                video.video_metadata = metadata
                db.session.commit()
                print("✓")
                success += 1
            else:
                failed += 1

        print(f"\nDone: {success} updated, {failed} failed")


if __name__ == "__main__":
    sync_metadata()
