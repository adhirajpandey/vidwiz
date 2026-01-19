import os
import sys
from flask import Flask, send_from_directory
from flask_cors import CORS

from vidwiz.routes.video_routes import video_bp
from vidwiz.routes.notes_routes import notes_bp
from vidwiz.routes.core_routes import core_bp
from vidwiz.routes.user_routes import user_bp
from vidwiz.routes.tasks_routes import tasks_bp
from vidwiz.routes.frontend_routes import frontend_bp

from vidwiz.shared.models import db
from sqlalchemy import text

from dotenv import load_dotenv
from vidwiz.shared.logging import get_logger, configure_logging
from vidwiz.shared.utils import check_required_env_vars

load_dotenv()

logger = get_logger("vidwiz.app")


def create_app(config=None):
    configure_logging()

    app = Flask(__name__, static_folder="dist", static_url_path="/static")

    DB_URL = os.getenv("DB_URL", None)
    SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_key")
    ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", None)

    AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", None)
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", None)

    SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", None)
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", None)
    JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", None)

    # Only check and set required env vars if no config dict is provided - for test etc
    if config is None:
        check_required_env_vars()
        app.config["SQLALCHEMY_DATABASE_URI"] = DB_URL
        app.config["SECRET_KEY"] = SECRET_KEY
        app.config["AWS_ACCESS_KEY_ID"] = AWS_ACCESS_KEY_ID
        app.config["AWS_SECRET_ACCESS_KEY"] = AWS_SECRET_ACCESS_KEY
        app.config["AWS_REGION"] = AWS_REGION
        app.config["SQS_QUEUE_URL"] = SQS_QUEUE_URL
        app.config["S3_BUCKET_NAME"] = S3_BUCKET_NAME
        app.config["ADMIN_TOKEN"] = ADMIN_TOKEN
        app.config["JWT_EXPIRY_HOURS"] = JWT_EXPIRY_HOURS
        app.config["GOOGLE_CLIENT_ID"] = GOOGLE_CLIENT_ID
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_recycle": 7200,
        }
        
    else:
        app.config.update(config)

    db.init_app(app)

    CORS(app)

    app.register_blueprint(core_bp, url_prefix="/api")
    app.register_blueprint(user_bp, url_prefix="/api")
    app.register_blueprint(video_bp, url_prefix="/api")
    app.register_blueprint(notes_bp, url_prefix="/api")
    app.register_blueprint(tasks_bp, url_prefix="/api")
    app.register_blueprint(frontend_bp)

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
