from urllib.parse import parse_qs, urlparse
import re


YOUTUBE_VIDEO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{11}$")


def normalize_youtube_video_id(value: str) -> str:
    if not value or not value.strip():
        raise ValueError("video_id cannot be empty")

    trimmed = value.strip()

    if "list=" in trimmed:
        raise ValueError("playlist URLs are not supported")

    if YOUTUBE_VIDEO_ID_PATTERN.match(trimmed):
        return trimmed

    url_to_parse = trimmed
    if not re.match(r"^https?://", url_to_parse):
        url_to_parse = f"https://{url_to_parse}"

    parsed = urlparse(url_to_parse)
    hostname = (parsed.hostname or "").lower()
    if hostname.startswith("www."):
        hostname = hostname[4:]

    if "youtube.com" in hostname and parsed.path == "/watch":
        video_id = parse_qs(parsed.query).get("v", [None])[0]
        if video_id and YOUTUBE_VIDEO_ID_PATTERN.match(video_id):
            return video_id

    if "youtube.com" in hostname:
        for prefix in ("/shorts/", "/live/", "/embed/"):
            if parsed.path.startswith(prefix):
                video_id = parsed.path.split(prefix, 1)[1].split("/")[0]
                if video_id and YOUTUBE_VIDEO_ID_PATTERN.match(video_id):
                    return video_id

    if hostname == "youtu.be":
        video_id = parsed.path.lstrip("/").split("/")[0]
        if video_id and YOUTUBE_VIDEO_ID_PATTERN.match(video_id):
            return video_id

    raise ValueError("video_id must be a valid YouTube video ID")
