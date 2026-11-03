import json

from src.shared.aws import aws_client


def send_job(queue_url: str, payload: dict) -> None:
    """Send one job to an SQS queue; raises when SQS rejects it."""
    aws_client("sqs").send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
