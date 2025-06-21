from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy.sql import func
import os

db = SQLAlchemy()


class Note(db.Model):
    __tablename__ = os.getenv("TABLE_NAME", "vidwiz")

    id = Column(Integer, primary_key=True)
    video_id = Column(Text, nullable=False)
    video_title = Column(Text, nullable=False)
    note_timestamp = Column(Text, nullable=False)
    note = Column(Text)
    ai_note = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now()
    )
