"""
WSGI entry point for production deployment with Gunicorn.
"""

from vidwiz.app import create_app, verify_database_connection
from vidwiz.logging_config import configure_logging, get_logger

# Configure logging for WSGI context
configure_logging()
logger = get_logger("vidwiz.wsgi")

# Create the application instance for WSGI servers
app = create_app()

# Ensure database tables are created when running through WSGI
verify_database_connection(app)
logger.info("WSGI app initialized and database verified.")

if __name__ == "__main__":
    app.run()
