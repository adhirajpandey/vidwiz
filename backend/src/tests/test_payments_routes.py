import pytest

from src.config import settings


@pytest.mark.asyncio
async def test_list_credit_products(client):
    response = await client.get("/v2/payments/products")
    assert response.status_code == 200
    payload = response.json()
    assert "products" in payload
    assert len(payload["products"]) == len(settings.dodo_credit_products)
    first = payload["products"][0]
    assert "product_id" in first
    assert "credits" in first
    assert "price_inr" in first
    assert "price_per_credit" in first
