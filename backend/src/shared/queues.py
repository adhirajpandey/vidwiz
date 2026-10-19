import json

import boto3

from src.config import settings


def send_job(queue_url: str, payload: dict) -> None:
    """Send one job to an SQS queue; raises when SQS rejects it."""
    sqs = boto3.client(
        "sqs",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    sqs.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
