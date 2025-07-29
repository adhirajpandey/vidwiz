from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, Text, TIMESTAMP, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func


db = SQLAlchemy()


class Video(db.Model):
    __tablename__ = "videos"
    id = Column(Integer, primary_key=True)
    video_id = Column(Text, unique=True, nullable=False)
    title = Column(Text, nullable=False)
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

    video = relationship("Video", back_populates="notes")


class User(db.Model):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(Text, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
