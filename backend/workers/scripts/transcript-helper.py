import os
import sys
import argparse
import logging
from typing import List, Dict, Optional

import requests
from youtube_transcript_api import YouTubeTranscriptApi

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vidwiz.transcript_helper")


def get_auth_token() -> str:
    """Load ADMIN_TOKEN from environment. Fail fast if missing."""
    token = os.environ.get("ADMIN_TOKEN")
    if not token:
        logger.error("ADMIN_TOKEN environment variable is not set")
        sys.exit(1)
    return token


def parse_arguments() -> int:
    """Parse command line arguments and return timeout."""
    parser = argparse.ArgumentParser(description="YouTube transcript helper for VidWiz")
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Long poll timeout in seconds (default: 30)",
    )

    args = parser.parse_args()
    return args.timeout


class TranscriptHelper:
    """Helper that polls for transcript tasks and submits results."""

    def __init__(self, auth_token: str, timeout_seconds: int, api_url: str) -> None:
        self.timeout_seconds = timeout_seconds
        self.headers = {"Authorization": f"Bearer {auth_token}"}
        # Ensure api_url doesn't end with slash
        self.base_url = api_url.rstrip("/")
        self.tasks_url = f"{self.base_url}/v2/internal/tasks"

    @staticmethod
    def _replace_key_names(transcript: List[Dict]) -> List[Dict]:
        """Replace 'start' key with 'offset' in the transcript."""
        for obj in transcript:
            if "start" in obj:
                obj["offset"] = obj.pop("start")
        return transcript

    def get_video_transcript(self, video_id: str) -> List[Dict]:
        """Fetch the transcript for a given video ID using YouTubeTranscriptApi."""
        transcript = (
            YouTubeTranscriptApi().fetch(video_id, languages=["en", "hi"]).to_raw_data()
        )
        return self._replace_key_names(transcript)

    def get_transcript_task(self) -> Optional[Dict]:
        # Polling for "fetch_transcript" task type
        params = {
            "type": "transcript",
            "timeout": self.timeout_seconds,
        }

        try:
            response = requests.get(
                self.tasks_url,
                headers=self.headers,
                params=params,
                timeout=(10, self.timeout_seconds + 10),
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
        transcript: Optional[List[Dict]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Send task result - either success with transcript or failure with error message."""
        success = transcript is not None and error_message is None

        data: Dict = {
            "video_id": video_id,
            "success": success,
        }

        if success:
            data["transcript"] = transcript
        else:
            data["error_message"] = error_message

        logger.info(f"Sending task result for task_id={task_id}")

        url = f"{self.tasks_url}/{task_id}/result"

        try:
            response = requests.post(url, json=data, headers=self.headers)
            response.raise_for_status()
            logger.info(
                f"Task result submitted successfully: {response.json().get('status')}"
            )
        except requests.RequestException as e:
            logger.error(f"Failed to submit task result: {e}")
            if hasattr(e, "response") and e.response:
                logger.error(f"Response content: {e.response.text}")  # type: ignore

    def run(self) -> None:
        """Continuously poll for transcript tasks and process them."""
        logger.info(
            f"Starting transcript helper with timeout: {self.timeout_seconds}s, URL: {self.tasks_url}"
        )

        while True:
            try:
                task_data = self.get_transcript_task()
                if not task_data or "task_id" not in task_data:
                    # logger.info("No task available, waiting for next poll...") # Can be noisy
                    continue

                task_id = task_data.get("task_id")
                # In new schema task details are nested under task_details
                video_id = task_data.get("task_details", {}).get("video_id")

                if not video_id:
                    logger.error(f"Received task {task_id} without video_id in details")
                    continue

                logger.info(f"Received task: {task_id}, video_id: {video_id}")

                try:
                    transcript = self.get_video_transcript(video_id)
                    self.send_task_result(task_id, video_id, transcript=transcript)
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Error processing video {video_id}: {e}")
                    self.send_task_result(task_id, video_id, error_message=str(e))

            except Exception as e:  # noqa: BLE001
                logger.error(f"Error in main loop: {e}")
                import time

                time.sleep(5)  # Backoff on error
                continue


def main() -> None:
    auth_token = get_auth_token()

    parser = argparse.ArgumentParser(description="YouTube transcript helper for VidWiz")
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Long poll timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="https://api.vidwiz.online",
        help="Base API URL (default: https://api.vidwiz.online)",
    )

    args = parser.parse_args()

    helper = TranscriptHelper(
        auth_token=auth_token, timeout_seconds=args.timeout, api_url=args.api_url
    )
    helper.run()


if __name__ == "__main__":
    main()
