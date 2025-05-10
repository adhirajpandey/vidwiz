from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, Text, TIMESTAMP
from sqlalchemy.sql import func
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
import os
from functools import wraps

load_dotenv()

db = SQLAlchemy()


# SQLAlchemy Model
class Note(db.Model):
    __tablename__ = os.getenv("TABLE_NAME", "notes")  # default for testing

    id = Column(Integer, primary_key=True)
    video_id = Column(Text, nullable=False)
    video_title = Column(Text)
    note_timestamp = Column(Text, nullable=False)
    note = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    updated_at = Column(
        TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return f"<Note(id={self.id}, video_id='{self.video_id}', timestamp={self.note_timestamp})>"


# Pydantic Schemas
class NoteCreate(BaseModel):
    video_id: str
    video_title: Optional[str] = None
    note_timestamp: str
    note: Optional[str] = None


class NoteRead(BaseModel):
    id: int
    video_id: str
    video_title: Optional[str]
    note_timestamp: str
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# Factory function
def create_app(test_config=None):
    app = Flask(__name__)

    DB_URL = os.getenv("DB_URL")
    AUTH_TOKEN = os.getenv("AUTH_TOKEN")

    if not test_config:
        if not all([DB_URL, AUTH_TOKEN]):
            raise ValueError(
                "DB_URL and AUTH_TOKEN must be set in the environment variables."
            )
        app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
        app.config["AUTH_TOKEN"] = AUTH_TOKEN
    else:
        # Use test configuration
        app.config.update(test_config)

    db.init_app(app)

    # Authentication decorator
    def token_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            token = request.headers.get("Authorization")
            if token is None or token != f"Bearer {app.config['AUTH_TOKEN']}":
                return jsonify({"error": "Unauthorized"}), 401
            return f(*args, **kwargs)

        return decorated_function

    # Routes
    @app.route("/notes", methods=["POST"])
    @token_required
    def create_note():
        try:
            data = request.json
            print(f"INFO: Notes POST request data: {data}")
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

    @app.route("/notes/<video_id>", methods=["GET"])
    @token_required
    def get_notes_by_video(video_id):
        try:
            print(f"INFO: Notes GET request for video_id: {video_id}")
            if not video_id:
                return jsonify({"error": "video_id is required"}), 400
            notes = Note.query.filter_by(video_id=video_id).all()
            if not notes:
                return jsonify({"error": "No notes found for the given video_id"}), 404
            return jsonify(
                [NoteRead.model_validate(note).model_dump() for note in notes]
            ), 200
        except Exception as e:
            print(f"Error fetching notes: {e}")
            return jsonify({"error": "Internal Server Error"}), 500

    @app.route("/dashboard", methods=["GET"])
    def get_dashboard_page():
        try:
            return render_template("dashboard.html")
        except Exception as e:
            print(f"Error rendering dashboard: {e}")
            return jsonify({"error": "Internal Server Error"}), 500

    @app.route("/dashboard/<video_id>", methods=["GET"])
    def get_video_page(video_id):
        try:
            return render_template("video.html")
        except Exception as e:
            print(f"Error rendering video notes page: {e}")
            return jsonify({"error": "Internal Server Error"}), 500

    @app.route("/search", methods=["GET"])
    @token_required
    def get_search_results():
        try:
            query = request.args.get("query", None)
            print(f"INFO: Search query: {query}")

            if query is None:
                return jsonify({"error": "Query parameter is required"}), 400

            result = (
                db.session.query(Note.video_id, Note.video_title)
                .filter(Note.video_title.ilike(f"%{query}%"))
                .distinct()
                .all()
            )
            if not result:
                return jsonify({"error": "No videos found matching the query"}), 404
            all_videos = [
                {"video_id": video.video_id, "video_title": video.video_title}
                for video in result
            ]

            return jsonify(all_videos), 200
        except Exception as e:
            print(f"Error rendering dashboard: {e}")
            return jsonify({"error": "Internal Server Error"}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run()
