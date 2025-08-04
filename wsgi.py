"""
WSGI entry point for production deployment with Gunicorn.
"""

from vidwiz.app import create_app

# Create the application instance for WSGI servers
app = create_app()

if __name__ == "__main__":
    app.run()
