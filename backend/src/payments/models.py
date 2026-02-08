from datetime import datetime

from sqlalchemy import Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base

PROVIDER_DODO = "dodo"
PURCHASE_STATUS_PENDING = "pending"
PURCHASE_STATUS_COMPLETED = "completed"
PURCHASE_STATUS_FAILED = "failed"
PURCHASE_STATUS_CANCELLED = "cancelled"


class CreditPurchase(Base):
    __tablename__ = "credit_purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False, default=PROVIDER_DODO)
    provider_session_id: Mapped[str] = mapped_column(Text, nullable=False)
    provider_payment_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    credits_amount: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default=PURCHASE_STATUS_PENDING
    )
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now(), server_default=func.now()
    )
