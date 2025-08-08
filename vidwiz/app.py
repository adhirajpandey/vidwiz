import os
import sys
from flask import Flask

from vidwiz.routes.video_routes import video_bp
from vidwiz.routes.notes_routes import notes_bp
from vidwiz.routes.core_routes import core_bp
from vidwiz.routes.admin_routes import admin_bp
from vidwiz.routes.tasks_routes import tasks_bp

from vidwiz.shared.models import db
from sqlalchemy import text

from dotenv import load_dotenv
from vidwiz.shared.logging import get_logger, configure_logging

load_dotenv()

logger = get_logger("vidwiz.app")


def create_app(test_config=None):
    # Ensure logging is configured for the app context
    configure_logging()

    app = Flask(__name__)
    DB_URL = os.getenv("DB_URL")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key")
    LAMBDA_URL = os.getenv("LAMBDA_URL")

    if not test_config:
        if not DB_URL:
            raise ValueError("DB_URL must be set in the environment variables.")
        if not LAMBDA_URL:
            raise ValueError("LAMBDA_URL must be set in the environment variables.")
        app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
        app.config["SECRET_KEY"] = SECRET_KEY
        app.config["LAMBDA_URL"] = LAMBDA_URL

    else:
        app.config.update(test_config)

    db.init_app(app)

    app.register_blueprint(core_bp)
    app.register_blueprint(video_bp)
    app.register_blueprint(notes_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(tasks_bp)

    return app


def verify_database_connection(app):
    """Check DB connectivity; exit if unavailable."""
    with app.app_context():
        try:
            db.session.execute(text("SELECT 1"))
            db.create_all()
            logger.info("Database connected and tables ready.")
        except Exception as e:
            logger.exception(f"Failed to connect to the database: {e}")
            sys.exit(1)


def main():
    app = create_app()
    verify_database_connection(app)
    logger.info("Starting Flask development server on 0.0.0.0 with debug=True")
    app.run(debug=True, host="0.0.0.0")


if __name__ == "__main__":
    main()
