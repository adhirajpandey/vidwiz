from dataclasses import dataclass

from src.config import settings


@dataclass(frozen=True)
class CreditProduct:
    product_id: str
    credits: int
    name: str
    price_inr: int


def get_credit_product(product_id: str) -> CreditProduct | None:
    for item in settings.dodo_credit_products:
        credits = item.credits
        name = item.name or f"{credits} Credits"
        product = CreditProduct(
            product_id=item.product_id,
            credits=credits,
            name=name,
            price_inr=item.price_inr,
        )
        if product.product_id == product_id:
            return product
    return None
