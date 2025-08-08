from youtube_transcript_api import YouTubeTranscriptApi
import requests
from vidwiz.logging_config import configure_logging, get_logger
import argparse

configure_logging()
logger = get_logger("vidwiz.transcript_helper")


def parse_arguments():
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


TASK_ENDPOINT = "https://vidwiz.adhirajpandey.tech/tasks/transcript"
AUTH_TOKEN, LONG_POLL_TIMEOUT = parse_arguments()


def replace_key_names(transcript):
    """
    Replace 'start' key with 'offset' in the transcript.
    """
    for obj in transcript:
        if "start" in obj:
            obj["offset"] = obj.pop("start")
    return transcript


def get_video_transcript(video_id):
    """Fetch the transcript for a given video ID using YouTubeTranscriptApi."""
    transcript = (
        YouTubeTranscriptApi().fetch(video_id, languages=["en", "hi"]).to_raw_data()
    )
    return replace_key_names(transcript)


def get_transcript_task(timeout):
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    response = requests.get(TASK_ENDPOINT, headers=headers, params={"timeout": timeout})
    if response.status_code == 204:
        return None

    response.raise_for_status()

    return response.json()


def send_task_result(task_id, video_id, transcript=None, error_message=None):
    """Send task result - either success with transcript or failure with error message."""
    success = transcript is not None and error_message is None

    data = {
        "task_id": task_id,
        "video_id": video_id,
        "success": success,
    }

    if success:
        data["transcript"] = transcript
    else:
        data["error_message"] = error_message

    logger.info(f"Sending task result: {data}")

    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    response = requests.post(TASK_ENDPOINT, json=data, headers=headers)
    response.raise_for_status()


def main():
    """Main function to continuously poll for transcript tasks and process them."""
    logger.info(f"Starting transcript helper with timeout: {LONG_POLL_TIMEOUT}s")

    while True:
        try:
            response = get_transcript_task(LONG_POLL_TIMEOUT)
            if not response or "task_id" not in response:
                logger.info("No task available, waiting for next poll...")
                continue

            task_id = response.get("task_id")
            video_id = response.get("task_details", {}).get("video_id")

            logger.info(f"Received task: {task_id}, video_id: {video_id}")

            try:
                transcript = get_video_transcript(video_id)
                send_task_result(task_id, video_id, transcript=transcript)
            except Exception as e:
                send_task_result(task_id, video_id, error_message=str(e))

        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            continue


if __name__ == "__main__":
    main()
