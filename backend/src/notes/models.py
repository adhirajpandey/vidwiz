from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.video_id"), nullable=False)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_by_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now(), server_default=func.now()
    )
    user_id: Mapped[int] = mapped_column(nullable=False)

    video = relationship("Video", back_populates="notes")
