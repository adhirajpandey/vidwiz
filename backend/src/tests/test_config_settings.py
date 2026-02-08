import importlib

import pytest
from pydantic import ValidationError


REQUIRED_ENV_VARS = [
    "ENVIRONMENT",
    "SECRET_KEY",
    "ADMIN_TOKEN",
    "GOOGLE_CLIENT_ID",
    "SQS_AI_NOTE_QUEUE_URL",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "DODO_PAYMENTS_API_KEY",
    "DODO_PAYMENTS_WEBHOOK_KEY",
    "DODO_PAYMENTS_ENVIRONMENT",
    "DODO_PAYMENTS_RETURN_URL",
    "DODO_CREDIT_PRODUCTS",
]


def _set_required_env(monkeypatch):
    for key in REQUIRED_ENV_VARS:
        if key == "DODO_CREDIT_PRODUCTS":
            monkeypatch.setenv(
                key,
                '[{"product_id":"pdt_test","credits":200,"price_inr":20,"name":"200 Credits"}]',
            )
        else:
            monkeypatch.setenv(key, "test-value")


@pytest.mark.parametrize("missing_key", REQUIRED_ENV_VARS)
def test_settings_requires_env_vars(monkeypatch, missing_key):
    _set_required_env(monkeypatch)
    monkeypatch.delenv(missing_key, raising=False)

    import src.config as config_module

    with pytest.raises(ValidationError):
        importlib.reload(config_module)

    # Restore to a valid env to avoid impacting other tests.
    if missing_key == "DODO_CREDIT_PRODUCTS":
        monkeypatch.setenv(
            missing_key,
            '[{"product_id":"pdt_test","credits":200,"price_inr":20,"name":"200 Credits"}]',
        )
    else:
        monkeypatch.setenv(missing_key, "test-value")
    importlib.reload(config_module)
