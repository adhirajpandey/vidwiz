import enum
from datetime import datetime

from sqlalchemy import JSON, Enum, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.database import Base


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False
    )
    task_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    worker_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=func.now(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=func.now(), onupdate=func.now(), server_default=func.now()
    )
