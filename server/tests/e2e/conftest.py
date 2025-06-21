import pytest
import sys
import os
import threading
import time

# Add the 'server' directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app import create_app, db


@pytest.fixture(scope="session")
def live_server():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        }
    )

    with app.app_context():
        db.create_all()

        server_thread = threading.Thread(target=app.run, kwargs={"port": 5000})
        server_thread.daemon = True
        server_thread.start()

        time.sleep(1)
        yield app

        db.session.remove()
        db.drop_all()
