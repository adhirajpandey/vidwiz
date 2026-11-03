import threading

import boto3
from botocore.config import Config

from src.config import settings

# These bound connecting and reading, not DNS: name lookups ignore socket timeouts.
_CONFIG = Config(
    connect_timeout=2,
    read_timeout=5,
    retries={"max_attempts": 2, "mode": "standard"},
)

_clients = {}
# boto3's default session is not safe to use from several threads at once.
_lock = threading.Lock()


def aws_client(service: str):
    """One client per service, so requests share its open connections."""
    with _lock:
        if service not in _clients:
            _clients[service] = boto3.client(
                service,
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                config=_CONFIG,
            )
        return _clients[service]
