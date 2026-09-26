"""Poll the internal API for transcript or metadata tasks and submit results."""

import argparse
import logging
import os
import sys
import time

import requests
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vidwiz.task_helper")
INTERNAL_API_URL_ENV_VAR = "VIDWIZ_INTERNAL_API_BASE_URL"
INTERNAL_API_TOKEN_ENV_VAR = "VIDWIZ_INTERNAL_API_ADMIN_TOKEN"
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


def fetch_transcript(video_id: str) -> list[dict]:
    """Fetch an English or Hindi transcript, renaming `start` to `offset`."""
    transcript = (
        YouTubeTranscriptApi().fetch(video_id, languages=["en", "hi"]).to_raw_data()
    )
    for item in transcript:
        if "start" in item:
            item["offset"] = item.pop("start")
    return transcript


def fetch_metadata(video_id: str) -> dict:
    """Fetch the video metadata fields stored by VidWiz."""
    options = {"quiet": True, "no_warnings": True}
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(
            f"https://www.youtube.com/watch?v={video_id}", download=False
        )
    return {field: info.get(field) for field in METADATA_FIELDS}


# The task type is also the result payload key.
TASKS = {"transcript": fetch_transcript, "metadata": fetch_metadata}


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
            return None

    def send_task_result(
        self,
        task_id: int,
        video_id: str,
        result: list | dict | None = None,
        error_message: str | None = None,
    ) -> None:
        """Send either a successful result or a failure message."""
        success = result is not None and error_message is None
        data: dict = {"video_id": video_id, "success": success}
        if success:
            data[self.task_type] = result
        else:
            data["error_message"] = error_message

        logger.info(f"Sending task result for task_id={task_id}, success={success}")
        try:
            response = requests.post(
                f"{self.tasks_url}/{task_id}/result", json=data, headers=self.headers
            )
            response.raise_for_status()
            logger.info(
                f"Task result submitted successfully: {response.json().get('status')}"
            )
        except requests.RequestException as e:
            logger.error(f"Failed to submit task result: {e}")
            if e.response is not None:
                logger.error(f"Response content: {e.response.text}")

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

                task_id = task_data.get("task_id")
                video_id = (task_data.get("task_details") or {}).get("video_id")
                if not video_id:
                    logger.error(f"Received task {task_id} without video_id in details")
                    continue

                logger.info(f"Received task: {task_id}, video_id: {video_id}")
                try:
                    self.send_task_result(
                        task_id, video_id, result=self.fetch(video_id)
                    )
                    logger.info(f"Successfully processed video: {video_id}")
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Failed to process video {video_id}: {e}")
                    self.send_task_result(task_id, video_id, error_message=str(e))
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
