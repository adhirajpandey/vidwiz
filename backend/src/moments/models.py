import enum
from datetime import datetime

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base
from src.shared.types import text_enum


class AiStatus(str, enum.Enum):
    NOT_REQUESTED = "not_requested"
    WAITING_TRANSCRIPT = "waiting_transcript"
    QUEUED = "queued"
    READY = "ready"
    FAILED = "failed"
    NO_TRANSCRIPT = "no_transcript"
    INSUFFICIENT_CREDITS = "insufficient_credits"


class ResolveStatus(str, enum.Enum):
    RESOLVING = "resolving"
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"


class CaptureSource(str, enum.Enum):
    PHONE = "phone"
    EXTENSION = "extension"
    WEB = "web"
    API = "api"
    LEGACY = "legacy"


class Moment(Base):
    __tablename__ = "moments"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # Null only while a title-only capture is being resolved, or if it failed.
    video_id: Mapped[str | None] = mapped_column(
        ForeignKey("videos.video_id"), nullable=True
    )
    at_seconds: Mapped[int] = mapped_column(nullable=False)
    quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    quote_start_seconds: Mapped[int | None] = mapped_column(nullable=True)
    ai_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_status: Mapped[AiStatus] = mapped_column(
        text_enum(AiStatus), nullable=False, default=AiStatus.NOT_REQUESTED
    )
    resolve_status: Mapped[ResolveStatus] = mapped_column(
        text_enum(ResolveStatus), nullable=False, default=ResolveStatus.RESOLVED
    )
    source: Mapped[CaptureSource] = mapped_column(
        text_enum(CaptureSource), nullable=False
    )
    pending_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    pending_channel: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now(), server_default=func.now()
    )

    video = relationship("Video", back_populates="moments")
