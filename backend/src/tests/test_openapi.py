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
