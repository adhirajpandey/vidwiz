"""
WSGI entry point for production deployment with Gunicorn.
"""

from vidwiz.app import create_app, verify_database_connection

# Create the application instance for WSGI servers
app = create_app()

# Ensure database tables are created when running through WSGI
verify_database_connection(app)

if __name__ == "__main__":
    app.run()
