from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, Text, TIMESTAMP, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum


db = SQLAlchemy()


class TaskStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(db.Model):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    task_type = Column(Text, nullable=False)
    status = Column(db.Enum(TaskStatus), default=TaskStatus.PENDING, nullable=False)
    task_details = Column(JSON)
    worker_details = Column(JSON)
    retry_count = Column(Integer, default=0)
    started_at = Column(TIMESTAMP(timezone=True))
    completed_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now()
    )


class Video(db.Model):
    __tablename__ = "videos"
    id = Column(Integer, primary_key=True)
    video_id = Column(Text, unique=True, nullable=False)
    title = Column(Text, nullable=False)
    video_metadata = Column(JSON, nullable=True)
    transcript_available = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now()
    )
    notes = relationship("Note", back_populates="video", cascade="all, delete-orphan")


class Note(db.Model):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True)
    video_id = Column(Text, ForeignKey("videos.video_id"), nullable=False)
    timestamp = Column(Text, nullable=False)
    text = Column(Text)
    generated_by_ai = Column(Boolean, default=False)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now()
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="notes")
    video = relationship("Video", back_populates="notes")


class User(db.Model):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=True)  # Store user's display name
    password_hash = Column(Text, nullable=True)  # Nullable for OAuth users
    google_id = Column(Text, unique=True, nullable=True)
    email = Column(Text, unique=True, nullable=True)
    profile_image_url = Column(Text, nullable=True)  # Store profile picture URL from Google
    long_term_token = Column(Text, nullable=True)
    profile_data = Column(JSON, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    notes = relationship("Note", back_populates="user", cascade="all, delete-orphan")
