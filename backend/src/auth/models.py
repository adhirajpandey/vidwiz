from datetime import datetime

from sqlalchemy import JSON, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_id: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    profile_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    long_term_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    credits_balance: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
