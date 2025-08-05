from youtube_transcript_api import YouTubeTranscriptApi
import requests

task_url = "http://localhost:5000/tasks/transcript"
token = "token"
headers = {"Authorization": f"Bearer {token}"}


def get_video_transcript(video_id):
    transcript = (
        YouTubeTranscriptApi().fetch(video_id, languages=["en", "hi"]).to_raw_data()
    )
    for obj in transcript:
        if "start" in obj:
            obj["offset"] = obj.pop("start")
    return transcript


def get_transcript_task():
    timeout = 3
    response = requests.get(task_url, headers=headers, params={"timeout": timeout})
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error fetching transcript task: {response.status_code}")
        return None


def send_success_result(task_id, video_id, transcript):
    data = {
        "task_id": task_id,
        "video_id": video_id,
        "transcript": transcript,
        "success": True,
    }
    response = requests.post(task_url, json=data, headers=headers)
    if response.status_code == 200:
        print("Transcript result submitted successfully.")
    else:
        print(f"Error submitting transcript result: {response.status_code}")


def send_failure_result(task_id, video_id, error_message):
    data = {
        "task_id": task_id,
        "video_id": video_id,
        "success": False,
        "error_message": error_message,
    }
    response = requests.post(task_url, json=data, headers=headers)
    if response.status_code == 200:
        print("Error result submitted successfully.")
    else:
        print(f"Error submitting error result: {response.status_code}")


def main():
    while True:
        try:
            response = get_transcript_task()
            print("response:", response)
            if response:
                try:
                    transcript = get_video_transcript(
                        response["task_details"]["video_id"]
                    )
                    send_success_result(
                        response["task_id"],
                        response["task_details"]["video_id"],
                        transcript,
                    )
                except Exception as e:
                    send_failure_result(
                        response["task_id"],
                        response["task_details"]["video_id"],
                        str(e),
                    )
        except Exception as e:
            print(f"Error in main loop: {e}")
            print("Request timed out, retrying...")
            continue


if __name__ == "__main__":
    main()
