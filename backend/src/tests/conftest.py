from collections.abc import Generator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.auth import models as auth_models  # noqa: F401
from src.conversations import models as conversation_models  # noqa: F401
from src.internal import models as internal_models  # noqa: F401
from src.notes import models as notes_models  # noqa: F401
from src.videos import models as video_models  # noqa: F401
from src.database import Base, get_db
from src.main import create_app
from src.config import settings


TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"


def _setup_settings() -> None:
    settings.secret_key = "test-secret"
    settings.jwt_expiry_hours = 1
    settings.google_client_id = "test-google-client-id"
    settings.admin_token = "test-admin-token"


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(engine) -> Generator:
    TestingSessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def app(db_session):
    _setup_settings()
    app = create_app()

    def _get_db() -> Generator:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db
    return app


@pytest.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
