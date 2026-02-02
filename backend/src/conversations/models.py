from datetime import datetime

from sqlalchemy import ForeignKey, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int | None] = mapped_column(nullable=True)
    guest_session_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now(), server_default=func.now()
    )

    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column(
        "metadata", JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )

    conversation = relationship("Conversation", back_populates="messages")
