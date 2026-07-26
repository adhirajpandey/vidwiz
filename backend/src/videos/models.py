from datetime import datetime

from sqlalchemy import Boolean, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    transcript_available: Mapped[bool] = mapped_column(Boolean, default=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    miscellaneous_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now(), server_default=func.now()
    )

    notes = relationship("Note", back_populates="video", cascade="all, delete-orphan")

    @property
    def suggested_questions(self) -> list[str] | None:
        questions = (self.miscellaneous_data or {}).get("suggested_questions")
        if not isinstance(questions, list) or len(questions) != 3:
            return None
        if not all(
            isinstance(question, str) and question.strip() for question in questions
        ):
            return None
        normalized = [question.strip() for question in questions]
        if len({question.casefold() for question in normalized}) != 3:
            return None
        return normalized
