import threading

import boto3

from src.shared import queues
from src.shared.aws import aws_client


def test_client_is_built_once_per_service_with_timeouts(monkeypatch):
    built = []

    def fake_client(service, **kwargs):
        built.append((service, kwargs["config"]))
        return object()

    monkeypatch.setattr(boto3, "client", fake_client)

    sqs = aws_client("sqs")
    assert aws_client("sqs") is sqs
    assert aws_client("s3") is not sqs
    assert [service for service, _ in built] == ["sqs", "s3"]
    config = built[0][1]
    assert config.connect_timeout == 2
    assert config.read_timeout == 5
    assert config.retries == {"total_max_attempts": 2, "mode": "standard"}


def test_concurrent_first_use_builds_one_client(monkeypatch):
    built = []

    def slow_client(service, **_kwargs):
        built.append(service)
        threading.Event().wait(0.05)
        return object()

    monkeypatch.setattr(boto3, "client", slow_client)
    threads = [threading.Thread(target=aws_client, args=("sqs",)) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert built == ["sqs"]


def test_send_job_reuses_the_client(monkeypatch):
    built, sent = [], []

    class Sqs:
        def send_message(self, QueueUrl, MessageBody):
            sent.append((QueueUrl, MessageBody))

    def fake_client(service, **_kwargs):
        built.append(service)
        return Sqs()

    monkeypatch.setattr(boto3, "client", fake_client)

    queues.send_job("queue", {"id": 1})
    queues.send_job("queue", {"id": 2})

    assert built == ["sqs"]
    assert sent == [("queue", '{"id": 1}'), ("queue", '{"id": 2}')]
