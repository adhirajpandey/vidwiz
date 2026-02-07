from dataclasses import dataclass
import json

from src.config import settings


@dataclass(frozen=True)
class CreditProduct:
    product_id: str
    credits: int
    name: str


DEFAULT_CREDIT_PRODUCTS: list[CreditProduct] = [
    CreditProduct(product_id="credits_100", credits=100, name="100 Credits"),
]


def _load_products_from_env() -> list[CreditProduct] | None:
    if not settings.dodo_credit_products:
        return None

    try:
        payload = json.loads(settings.dodo_credit_products)
    except json.JSONDecodeError as exc:
        raise ValueError("DODO_CREDIT_PRODUCTS must be valid JSON") from exc

    if not isinstance(payload, list):
        raise ValueError("DODO_CREDIT_PRODUCTS must be a JSON list")

    products: list[CreditProduct] = []
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("DODO_CREDIT_PRODUCTS entries must be objects")
        product_id = item.get("product_id")
        credits = item.get("credits")
        name = item.get("name") or f"{credits} Credits"
        if not product_id or not isinstance(product_id, str):
            raise ValueError("DODO_CREDIT_PRODUCTS entry missing product_id")
        if not isinstance(credits, int) or credits <= 0:
            raise ValueError("DODO_CREDIT_PRODUCTS entry has invalid credits")
        products.append(
            CreditProduct(product_id=product_id, credits=credits, name=name)
        )

    return products


def get_credit_products() -> list[CreditProduct]:
    return _load_products_from_env() or DEFAULT_CREDIT_PRODUCTS


def get_credit_product(product_id: str) -> CreditProduct | None:
    for product in get_credit_products():
        if product.product_id == product_id:
            return product
    return None
