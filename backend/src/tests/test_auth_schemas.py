import pytest
from pydantic import ValidationError

from src.auth.schemas import AuthLoginRequest, AuthRegisterRequest, UserProfileUpdate


def test_register_schema_normalizes_email_and_name():
    payload = AuthRegisterRequest.model_validate(
        {
            "email": "  Mixed@Example.com ",
            "password": "password123",
            "name": "  Mixed User  ",
        }
    )
    assert payload.email == "mixed@example.com"
    assert payload.name == "Mixed User"


def test_register_schema_rejects_blank_name():
    with pytest.raises(ValidationError):
        AuthRegisterRequest.model_validate(
            {
                "email": "bad@example.com",
                "password": "password123",
                "name": "   ",
            }
        )


def test_login_schema_normalizes_email():
    payload = AuthLoginRequest.model_validate(
        {"email": "  LOGIN@Example.com ", "password": "password123"}
    )
    assert payload.email == "login@example.com"


def test_update_profile_rejects_short_name():
    with pytest.raises(ValidationError):
        UserProfileUpdate.model_validate({"name": "x"})


def test_update_profile_trims_name():
    payload = UserProfileUpdate.model_validate({"name": "  Valid Name  "})
    assert payload.name == "Valid Name"
