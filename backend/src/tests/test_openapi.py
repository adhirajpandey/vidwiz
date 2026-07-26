import pytest


@pytest.mark.asyncio
async def test_openapi_and_swagger_are_available(client):
    schema_response = await client.get("/openapi.json")
    docs_response = await client.get("/docs")
    redoc_response = await client.get("/redoc")

    assert schema_response.status_code == 200
    assert schema_response.json()["info"] == {
        "title": "VidWiz API",
        "description": (
            "Create timestamped YouTube notes and use transcript-grounded AI chat."
        ),
        "version": "2.0.0",
    }
    assert docs_response.status_code == 200
    assert "swagger-ui" in docs_response.text.lower()
    assert redoc_response.status_code == 404


@pytest.mark.asyncio
async def test_openapi_describes_vidwiz_authentication(client):
    response = await client.get("/openapi.json")
    schema = response.json()

    assert schema["components"]["securitySchemes"] == {
        "BearerAuth": {
            "type": "http",
            "description": (
                "JWT access token. Long-term JWTs are accepted only by note creation."
            ),
            "scheme": "bearer",
            "bearerFormat": "JWT",
        },
        "GuestSession": {
            "type": "apiKey",
            "description": "Guest session ID for Wiz chat and video status streams.",
            "in": "header",
            "name": "X-Guest-Session-ID",
        },
        "AdminBearer": {
            "type": "http",
            "description": "Administrative token for internal worker endpoints.",
            "scheme": "bearer",
        },
    }

    assert "security" not in schema["paths"]["/v2/auth/register"]["post"]
    assert schema["paths"]["/v2/users/me"]["get"]["security"] == [{"BearerAuth": []}]
    assert schema["paths"]["/v2/conversations"]["post"]["security"] == [
        {"BearerAuth": []},
        {"GuestSession": []},
    ]
    assert schema["paths"]["/v2/internal/tasks"]["get"]["security"] == [
        {"AdminBearer": []}
    ]

    operation_parameters = [
        parameter
        for path in schema["paths"].values()
        for operation in path.values()
        if isinstance(operation, dict)
        for parameter in operation.get("parameters", [])
    ]
    assert all(
        parameter["name"].lower() != "authorization"
        for parameter in operation_parameters
    )
