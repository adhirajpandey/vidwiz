from typing import Any, Dict, List, Optional

import dispatch_service

logger = dispatch_service.logger


def extract_valid_video_id(key: str) -> Optional[str]:
    try:
        return key.split("/")[-1].replace(".json", "")
    except Exception as error:
        logger.error("Error extracting video_id", extra={"error": str(error)})
        return None


@logger.inject_lambda_context(log_event=True)
def lambda_handler(event: Dict[str, Any], context: Any) -> None:
    del context
    try:
        video_ids: List[str] = []
        is_s3_event = False

        records = event.get("Records", [])
        if records and isinstance(records, list):
            first = records[0]
            if "s3" in first and "object" in first["s3"]:
                is_s3_event = True
                key = first["s3"]["object"]["key"]
                video_id = extract_valid_video_id(key)
                if video_id:
                    video_ids.append(video_id)
                else:
                    logger.error(f"Could not extract video_id from key: {key}")

        incoming_ids = event.get("video_ids")
        if incoming_ids:
            if isinstance(incoming_ids, list):
                video_ids.extend(incoming_ids)
            else:
                logger.error("`video_ids` field must be a list of strings")

        if not video_ids:
            logger.error("No video IDs found in the event")
            return

        dispatch_service.dispatch_videos(video_ids, is_s3_event)
    except Exception as error:
        logger.error(f"Unhandled exception: {error}", exc_info=True)
        raise
