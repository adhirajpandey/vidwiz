from youtube_transcript_api import YouTubeTranscriptApi
import requests
import logging
import argparse
from typing import List, Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vidwiz.transcript_helper")

TASK_ENDPOINT = "https://vidwiz.online/api/tasks/transcript"


def parse_arguments() -> Tuple[str, int]:
    """Parse command line arguments and return auth token and timeout."""
    parser = argparse.ArgumentParser(description="YouTube transcript helper for VidWiz")
    parser.add_argument(
        "--auth-token", required=True, help="Authentication token for API requests"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Long poll timeout in seconds (default: 30)",
    )

    args = parser.parse_args()
    return args.auth_token, args.timeout


class TranscriptHelper:
    """Helper that polls for transcript tasks and submits results."""

    def __init__(self, auth_token: str, timeout_seconds: int) -> None:
        self.timeout_seconds = timeout_seconds
        self.headers = {"Authorization": f"Bearer {auth_token}"}

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
        response = requests.get(
            TASK_ENDPOINT,
            headers=self.headers,
            params={"timeout": self.timeout_seconds},
            timeout=(10, self.timeout_seconds + 10),  # for safe teardown
        )
        if response.status_code == 204:
            return None

        response.raise_for_status()
        return response.json()

    def send_task_result(
        self,
        task_id: str,
        video_id: str,
        transcript: Optional[List[Dict]] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Send task result - either success with transcript or failure with error message."""
        success = transcript is not None and error_message is None

        data: Dict = {
            "task_id": task_id,
            "video_id": video_id,
            "success": success,
        }

        if success:
            data["transcript"] = transcript
        else:
            data["error_message"] = error_message

        logger.info(f"Sending task result: {data}")

        response = requests.post(TASK_ENDPOINT, json=data, headers=self.headers)
        response.raise_for_status()

    def run(self) -> None:
        """Continuously poll for transcript tasks and process them."""
        logger.info(f"Starting transcript helper with timeout: {self.timeout_seconds}s")

        while True:
            try:
                response = self.get_transcript_task()
                if not response or "task_id" not in response:
                    logger.info("No task available, waiting for next poll...")
                    continue

                task_id = response.get("task_id")
                video_id = response.get("task_details", {}).get("video_id")

                logger.info(f"Received task: {task_id}, video_id: {video_id}")

                try:
                    transcript = self.get_video_transcript(video_id)
                    self.send_task_result(task_id, video_id, transcript=transcript)
                except Exception as e:  # noqa: BLE001
                    self.send_task_result(task_id, video_id, error_message=str(e))

            except Exception as e:  # noqa: BLE001
                logger.error(f"Error in main loop: {e}")
                continue


def main() -> None:
    auth_token, timeout = parse_arguments()
    helper = TranscriptHelper(auth_token=auth_token, timeout_seconds=timeout)
    helper.run()


if __name__ == "__main__":
    main()
