import enum
from datetime import datetime

from sqlalchemy import JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.shared.types import text_enum


class TranscriptStatus(str, enum.Enum):
    PENDING = "pending"
    READY = "ready"
    # Fetching failed for good; a new capture schedules another attempt.
    UNAVAILABLE = "unavailable"


class OverviewStatus(str, enum.Enum):
    # Waiting for the transcript.
    PENDING = "pending"
    QUEUED = "queued"
    READY = "ready"
    FAILED = "failed"
    NO_TRANSCRIPT = "no_transcript"


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    transcript_status: Mapped[TranscriptStatus] = mapped_column(
        text_enum(TranscriptStatus), nullable=False, default=TranscriptStatus.PENDING
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    overview_status: Mapped[OverviewStatus] = mapped_column(
        text_enum(OverviewStatus), nullable=False, default=OverviewStatus.PENDING
    )
    # When overview_status last changed; the sweep fails overviews queued too long.
    overview_status_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    miscellaneous_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now(), server_default=func.now()
    )

    moments = relationship("Moment", back_populates="video")

    @property
    def has_transcript(self) -> bool:
        return self.transcript_status == TranscriptStatus.READY

    @property
    def overview_model(self) -> str | None:
        return (self.miscellaneous_data or {}).get("overview_model")

    @property
    def key_points(self) -> list[dict] | None:
        points = (self.miscellaneous_data or {}).get("key_points")
        return points if isinstance(points, list) and points else None

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
