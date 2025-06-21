# app.py
from flask import Flask
from dotenv import load_dotenv
import os
import sys
from models import db
from routes import main_bp
from sqlalchemy import text

load_dotenv()


def create_app(test_config=None):
    app = Flask(__name__)
    DB_URL = os.getenv("DB_URL")
    AUTH_TOKEN = os.getenv("AUTH_TOKEN")
    LAMBDA_URL = os.getenv("LAMBDA_URL")
    AI_NOTE_TOGGLE = os.getenv("AI_NOTE_TOGGLE", "false").lower() == "true"

    if not test_config:
        if not all([DB_URL, AUTH_TOKEN]):
            raise ValueError(
                "DB_URL and AUTH_TOKEN must be set in the environment variables."
            )
        if AI_NOTE_TOGGLE and not LAMBDA_URL:
            raise ValueError(
                "LAMBDA_URL must be set in the environment variables when AI_NOTE_TOGGLE is enabled."
            )
        app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
        app.config["AUTH_TOKEN"] = AUTH_TOKEN
        app.config["LAMBDA_URL"] = LAMBDA_URL
        app.config["AI_NOTE_TOGGLE"] = AI_NOTE_TOGGLE

    else:
        app.config.update(test_config)

    db.init_app(app)
    app.register_blueprint(main_bp)

    return app


app = create_app()

with app.app_context():
    try:
        db.session.execute(text("SELECT 1"))
        db.create_all()
        print("✅ Database connected and tables ready.")
    except Exception as e:
        print(f"❌ Failed to connect to the database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    app.run()
