"""Poll the internal API for transcript, metadata, or title tasks and submit results."""

import argparse
import logging
import os
import sys
import time

import requests
import yt_dlp
from youtube_transcript_api import NoTranscriptFound, YouTubeTranscriptApi

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vidwiz.task_helper")
INTERNAL_API_URL_ENV_VAR = "VIDWIZ_INTERNAL_API_BASE_URL"
INTERNAL_API_TOKEN_ENV_VAR = "VIDWIZ_INTERNAL_API_ADMIN_TOKEN"
POLL_ERROR_BACKOFF_SECONDS = 5
TRANSCRIPT_LANGUAGES = ("en", "hi")
METADATA_FIELDS = (
    "id",
    "title",
    "uploader",
    "upload_date",
    "duration",
    "view_count",
    "like_count",
    "channel_url",
    "description",
    "thumbnail",
)


def pick_track(tracks):
    """Pick the English or Hindi track, else a regional variant such as en-GB."""
    try:
        return tracks.find_transcript(TRANSCRIPT_LANGUAGES)
    except NoTranscriptFound:
        for language in TRANSCRIPT_LANGUAGES:
            for track in tracks:
                if track.language_code.split("-")[0] == language:
                    return track
        raise


def fetch_transcript(video_id: str) -> dict:
    """Fetch the transcript and its language code, renaming `start` to `offset`."""
    track = pick_track(YouTubeTranscriptApi().list(video_id))
    transcript = track.fetch().to_raw_data()
    for item in transcript:
        if "start" in item:
            item["offset"] = item.pop("start")
    return {"transcript": transcript, "transcript_language": track.language_code}


def fetch_metadata(video_id: str) -> dict:
    """Fetch the video metadata fields stored by VidWiz."""
    options = {"quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(
            f"https://www.youtube.com/watch?v={video_id}", download=False
        )
    return {field: info.get(field) for field in METADATA_FIELDS}


TITLE_SEARCH_RESULTS = 5
JEV_DECISIONS_URL_ENV_VAR = "JEV_DECISIONS_URL"
JEV_MODEL_ENV_VAR = "JEV_MODEL"
DEFAULT_JEV_DECISIONS_URL = "https://openrouter.ai/api/alpha/decisions"
DEFAULT_JEV_MODEL = "typesafe/jev-1.14-20261014"
# Below this Jev confidence, the user picks from the candidates instead.
JEV_TITLE_CONFIDENCE = 0.75


def search_titles(title: str) -> list[dict]:
    options = {"quiet": True, "no_warnings": True, "extract_flat": True}
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(
            f"ytsearch{TITLE_SEARCH_RESULTS}:{title}", download=False
        )
    return [
        {
            "video_id": entry["id"],
            "title": entry.get("title"),
            "channel": entry.get("channel") or entry.get("uploader"),
        }
        for entry in info.get("entries") or []
        if entry.get("id")
    ]


def _normalized(text: str) -> str:
    """Letters and digits only, so punctuation and spacing don't block a match."""
    return "".join(char for char in text.casefold() if char.isalnum())


def _same(left: str | None, right: str | None) -> bool:
    return bool(left and right) and _normalized(left) == _normalized(right)


def jev_choose(
    title: str, channel: str | None, candidates: list[dict]
) -> tuple[str, float]:
    """Ask Jev which candidate the capture refers to; returns (video_id, confidence)."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    criteria = {
        f"v{index}": f"{candidate['title']} (channel: {candidate['channel'] or 'unknown'})"
        for index, candidate in enumerate(candidates)
    }
    response = requests.post(
        os.environ.get(JEV_DECISIONS_URL_ENV_VAR, DEFAULT_JEV_DECISIONS_URL),
        json={
            "model": os.environ.get(JEV_MODEL_ENV_VAR, DEFAULT_JEV_MODEL),
            "state": {
                "captured_title": title,
                "captured_channel": channel or "unknown",
                "note": "The title was read from a phone notification and may be truncated.",
            },
            "questions": {
                "video": {
                    "type": "choice",
                    "instructions": "Which search result is the video that was captured?",
                    "criteria": criteria,
                }
            },
        },
        headers={"Authorization": f"Bearer {key}", "X-Title": "VidWiz"},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    answer = (payload.get("answers") or payload.get("decisions") or {}).get(
        "video"
    ) or {}
    choice = answer.get("choice")
    if choice not in criteria:
        raise RuntimeError("Jev returned no valid choice")
    confidence = answer.get("confidence")
    if not isinstance(confidence, (int, float)):
        confidence = (answer.get("probabilities") or {}).get(choice, 0.0)
    return candidates[int(choice[1:])]["video_id"], float(confidence)


def resolve_title(title: str, channel: str | None = None) -> dict:
    """Find the video for a title-only capture.

    Exact matches decide first. When that is ambiguous, Jev chooses; a
    low-confidence or failed choice returns the candidates for the user to pick.
    """
    candidates = search_titles(title)
    if not candidates:
        raise LookupError("No YouTube results for this title")

    by_channel = [c for c in candidates if _same(c["channel"], channel)]
    exact = [c for c in (by_channel or candidates) if _same(c["title"], title)]
    if len(by_channel) == 1:
        return {"resolved": _resolved(by_channel[0])}
    if len(exact) == 1:
        return {"resolved": _resolved(exact[0])}

    try:
        video_id, confidence = jev_choose(title, channel, candidates)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Jev title choice failed: {e}")
        return {"candidates": candidates}
    logger.info(f"Jev title choice confidence={confidence:.2f}")
    if confidence >= JEV_TITLE_CONFIDENCE:
        chosen = next(c for c in candidates if c["video_id"] == video_id)
        return {"resolved": _resolved(chosen)}
    return {"candidates": candidates}


def _resolved(candidate: dict) -> dict:
    return {"video_id": candidate["video_id"], "title": candidate["title"]}


# Each task turns its details into the result payload fields.
TASKS = {
    "transcript": lambda details: {
        "video_id": details["video_id"],
        **fetch_transcript(details["video_id"]),
    },
    "metadata": lambda details: {
        "video_id": details["video_id"],
        "metadata": fetch_metadata(details["video_id"]),
    },
    "resolve_title": lambda details: resolve_title(
        details["title"], details.get("channel")
    ),
}


def _causes(error: Exception, depth: int = 5):
    """The error and what it wraps: yt-dlp keeps the original in exc_info."""
    seen = set()
    while error is not None and depth > 0 and id(error) not in seen:
        seen.add(id(error))
        yield error
        exc_info = getattr(error, "exc_info", None)
        wrapped = (
            exc_info[1] if isinstance(exc_info, tuple) and len(exc_info) > 1 else None
        )
        error = wrapped or error.__cause__ or error.__context__
        depth -= 1


def _kind(error: Exception) -> str | None:
    name = type(error).__name__
    text = str(error)
    if name in ("IpBlocked", "RequestBlocked", "AgeRestricted") or (
        "Sign in to confirm" in text
    ):
        return "youtube_blocked"
    if isinstance(error, requests.exceptions.ProxyError) or (
        "ProxyError" in text or "Unable to connect to proxy" in text
    ):
        return "proxy_error"
    if isinstance(error, (requests.exceptions.Timeout, TimeoutError)) or (
        "timed out" in text.lower()
    ):
        return "timeout"
    if isinstance(error, LookupError) or name in (
        "VideoUnavailable",
        "VideoUnplayable",
        "InvalidVideoId",
        "TranscriptsDisabled",
        "NoTranscriptFound",
    ):
        return "not_found"
    if isinstance(error, requests.exceptions.HTTPError):
        return "provider_error"
    return None


def error_kind(error: Exception) -> str:
    """Name the dependency that broke, using the API's bounded failure kinds."""
    for cause in _causes(error):
        kind = _kind(cause)
        if kind is not None:
            return kind
    return "worker_error"


def get_auth_token() -> str:
    """Load the internal API admin token. Fail fast if missing."""
    token = os.environ.get(INTERNAL_API_TOKEN_ENV_VAR)
    if not token:
        logger.error("%s environment variable is not set", INTERNAL_API_TOKEN_ENV_VAR)
        sys.exit(1)
    return token


def resolve_api_url(api_url_arg: str | None) -> str:
    """Resolve the internal API base URL from CLI or environment."""
    api_url = api_url_arg or os.environ.get(INTERNAL_API_URL_ENV_VAR)
    if not api_url:
        logger.error(
            "Internal API URL is not set. Pass --api-url or set %s.",
            INTERNAL_API_URL_ENV_VAR,
        )
        sys.exit(1)
    return api_url


class TaskHelper:
    """Poll for one task type and submit results."""

    def __init__(
        self, task_type: str, auth_token: str, timeout_seconds: int, api_url: str
    ) -> None:
        self.task_type = task_type
        self.fetch = TASKS[task_type]
        self.timeout_seconds = timeout_seconds
        self.headers = {"Authorization": f"Bearer {auth_token}"}
        self.tasks_url = f"{api_url.rstrip('/')}/v2/internal/tasks"

    def get_task(self) -> dict | None:
        """Long-poll for the next task; return None when no work is available."""
        try:
            response = requests.get(
                self.tasks_url,
                headers=self.headers,
                params={"type": self.task_type, "timeout": self.timeout_seconds},
                timeout=(10, self.timeout_seconds + 10),  # for safe teardown
            )
            if response.status_code == 204:
                return None
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error polling for task: {e}")
            time.sleep(POLL_ERROR_BACKOFF_SECONDS)
            return None

    def send_task_result(
        self, task_id: int, data: dict, correlation_id: str | None = None
    ) -> bool:
        """Send a result payload and return whether the API accepted it."""
        logger.info(
            "Sending task result task_id=%s success=%s correlation_id=%r",
            task_id,
            data["success"],
            correlation_id,
        )
        try:
            response = requests.post(
                f"{self.tasks_url}/{task_id}/result",
                json=data,
                headers={
                    **self.headers,
                    **({"X-Correlation-ID": correlation_id} if correlation_id else {}),
                },
            )
            response.raise_for_status()
            logger.info(
                "Task result submitted task_id=%s status=%s correlation_id=%r",
                task_id,
                response.json().get("status"),
                correlation_id,
            )
            return True
        except requests.RequestException as e:
            # The error names the URL and status; the response body may hold user data.
            logger.error(
                "Failed to submit result task_id=%s correlation_id=%r: %s",
                task_id,
                correlation_id,
                e,
            )
            return False

    def run(self) -> None:
        """Continuously poll for tasks and process them."""
        logger.info(
            f"Starting {self.task_type} helper with timeout: "
            f"{self.timeout_seconds}s, URL: {self.tasks_url}"
        )
        while True:
            try:
                task_data = self.get_task()
                if not task_data or "task_id" not in task_data:
                    continue

                task_id = task_data["task_id"]
                details = task_data.get("task_details") or {}
                correlation_id = details.get("correlation_id")
                logger.info(
                    "Received task task_id=%s correlation_id=%r",
                    task_id,
                    correlation_id,
                )
                try:
                    result = self.fetch(details)
                    result = {
                        **result,
                        "success": True,
                        **(
                            {"correlation_id": correlation_id} if correlation_id else {}
                        ),
                    }
                    if correlation_id:
                        accepted = self.send_task_result(
                            task_id, result, correlation_id
                        )
                    else:
                        accepted = self.send_task_result(task_id, result)
                    if accepted:
                        logger.info(
                            "Successfully processed task task_id=%s correlation_id=%r",
                            task_id,
                            correlation_id,
                        )
                    else:
                        logger.error(
                            "Result not accepted task_id=%s correlation_id=%r",
                            task_id,
                            correlation_id,
                        )
                except Exception as e:  # noqa: BLE001
                    logger.exception(
                        "Failed to process task %s video_id=%s moment_id=%s correlation_id=%r",
                        task_id,
                        details.get("video_id"),
                        details.get("moment_id"),
                        correlation_id,
                    )
                    failure = {
                        "video_id": details.get("video_id"),
                        "success": False,
                        "error_message": str(e),
                        "error_kind": error_kind(e),
                    }
                    if correlation_id:
                        self.send_task_result(task_id, failure, correlation_id)
                    else:
                        self.send_task_result(task_id, failure)
            except Exception as e:  # noqa: BLE001
                logger.error(f"Error in main loop: {e}")
                time.sleep(5)  # Backoff on error


def main() -> None:
    auth_token = get_auth_token()

    parser = argparse.ArgumentParser(description="YouTube task helper for VidWiz")
    parser.add_argument("task_type", choices=sorted(TASKS))
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Long poll timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default=None,
        help=f"Base API URL (overrides {INTERNAL_API_URL_ENV_VAR})",
    )
    args = parser.parse_args()
    api_url = resolve_api_url(args.api_url)
    logger.info("Using internal API base URL: %s", api_url.rstrip("/"))

    TaskHelper(args.task_type, auth_token, args.timeout, api_url).run()


if __name__ == "__main__":
    main()
