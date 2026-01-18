import yt_dlp
import requests
import logging
import argparse
from typing import Dict, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vidwiz.metadata_helper")

TASK_ENDPOINT = "https://vidwiz.adhirajpandey.tech/api/tasks/metadata"


def parse_arguments() -> Tuple[str, int]:
    """Parse command line arguments and return auth token and timeout."""
    parser = argparse.ArgumentParser(description="YouTube metadata helper for VidWiz")
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


class MetadataHelper:
    """Helper that polls for metadata tasks and submits results."""

    def __init__(self, auth_token: str, timeout_seconds: int) -> None:
        self.timeout_seconds = timeout_seconds
        self.headers = {"Authorization": f"Bearer {auth_token}"}

    def get_video_metadata(self, video_id: str) -> Optional[Dict]:
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
            logger.error(f"Failed to fetch metadata for {video_id}: {e}")
            raise

    def get_metadata_task(self) -> Optional[Dict]:
        """Poll for a metadata task from the API."""
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
        metadata: Optional[Dict] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Send task result - either success with metadata or failure with error message."""
        success = metadata is not None and error_message is None

        data: Dict = {
            "task_id": task_id,
            "video_id": video_id,
            "success": success,
        }

        if success:
            data["metadata"] = metadata
        else:
            data["error_message"] = error_message

        logger.info(f"Sending task result for video_id={video_id}, success={success}")

        response = requests.post(TASK_ENDPOINT, json=data, headers=self.headers)
        response.raise_for_status()

    def run(self) -> None:
        """Continuously poll for metadata tasks and process them."""
        logger.info(f"Starting metadata helper with timeout: {self.timeout_seconds}s")

        while True:
            try:
                response = self.get_metadata_task()
                if not response or "task_id" not in response:
                    logger.info("No task available, waiting for next poll...")
                    continue

                task_id = response.get("task_id")
                video_id = response.get("task_details", {}).get("video_id")

                logger.info(f"Received task: {task_id}, video_id: {video_id}")

                try:
                    metadata = self.get_video_metadata(video_id)
                    self.send_task_result(task_id, video_id, metadata=metadata)
                    logger.info(f"Successfully processed video: {video_id}")
                except Exception as e:  # noqa: BLE001
                    logger.error(f"Failed to process video {video_id}: {e}")
                    self.send_task_result(task_id, video_id, error_message=str(e))

            except Exception as e:  # noqa: BLE001
                logger.error(f"Error in main loop: {e}")
                continue


def main() -> None:
    auth_token, timeout = parse_arguments()
    helper = MetadataHelper(auth_token=auth_token, timeout_seconds=timeout)
    helper.run()


if __name__ == "__main__":
    main()
