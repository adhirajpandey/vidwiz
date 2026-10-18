from sqlalchemy import Computed, ForeignKey, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, deferred, mapped_column

from src.database import Base


class TranscriptChunk(Base):
    """A ~45-second transcript passage, stored so transcripts are searchable."""

    __tablename__ = "transcript_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[str] = mapped_column(
        ForeignKey("videos.video_id", ondelete="CASCADE"), nullable=False
    )
    idx: Mapped[int] = mapped_column(nullable=False)
    start_seconds: Mapped[int] = mapped_column(nullable=False)
    end_seconds: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    search: Mapped[str] = deferred(
        mapped_column(
            TSVECTOR, Computed("to_tsvector('english', text)", persisted=True)
        )
    )
