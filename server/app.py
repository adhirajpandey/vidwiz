from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy.sql import func
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
import os
from functools import wraps

# Load environment variables from .env (optional in tests)
load_dotenv()

db = SQLAlchemy()

# SQLAlchemy Model
class Note(db.Model):
    __tablename__ = os.getenv("TABLE_NAME", "notes")  # default for testing

    id = Column(Integer, primary_key=True)
    video_id = Column(Text, nullable=False)
    video_title = Column(Text)
    note_timestamp = Column(Text, nullable=False)
    note = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<Note(id={self.id}, video_id='{self.video_id}', timestamp={self.note_timestamp})>"

# Pydantic Schemas
class NoteCreate(BaseModel):
    video_id: str
    video_title: Optional[str] = None
    note_timestamp: str
    note: str

class NoteRead(BaseModel):
    id: int
    video_id: str
    video_title: Optional[str]
    note_timestamp: str
    note: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Factory function
def create_app(test_config=None):
    app = Flask(__name__)

    # Default config (production/dev)
    DB_URL = os.getenv('DB_URL')
    AUTH_TOKEN = os.getenv('AUTH_TOKEN')

    if not test_config:
        if not all([DB_URL, AUTH_TOKEN]):
            raise ValueError("DB_URL and AUTH_TOKEN must be set in the environment variables.")
        app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
        app.config['AUTH_TOKEN'] = AUTH_TOKEN
    else:
        # Use test configuration
        app.config.update(test_config)

    db.init_app(app)

    # Authentication decorator
    def token_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = request.headers.get('Authorization')
            if token is None or token != f"Bearer {app.config['AUTH_TOKEN']}":
                return jsonify({"error": "Unauthorized"}), 401
            return f(*args, **kwargs)
        return decorated_function

    # Routes
    @app.route('/notes', methods=['POST'])
    @token_required
    def create_note():
        try:
            data = request.json
            if not data:
                return jsonify({"error": "Request body must be JSON"}), 400
            try:
                note_data = NoteCreate(**data)
            except Exception as e:
                return jsonify({"error": f"Invalid data: {str(e)}"}), 400

            new_note = Note(**note_data.model_dump())
            db.session.add(new_note)
            db.session.commit()
            return jsonify(NoteRead.model_validate(new_note).model_dump()), 201
        except Exception as e:
            print(f"Error creating note: {e}")
            db.session.rollback()
            return jsonify({"error": "Internal Server Error"}), 500

    @app.route('/notes/<video_id>', methods=['GET'])
    @token_required
    def get_notes_by_video(video_id):
        try:
            if not video_id:
                return jsonify({"error": "video_id is required"}), 400
            notes = Note.query.filter_by(video_id=video_id).all()
            if not notes:
                return jsonify({"error": "No notes found for the given video_id"}), 404
            return jsonify([NoteRead.model_validate(note).model_dump() for note in notes]), 200
        except Exception as e:
            print(f"Error fetching notes: {e}")
            return jsonify({"error": "Internal Server Error"}), 500

    return app

# For local running
if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(debug=True)
