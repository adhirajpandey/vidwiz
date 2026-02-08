from collections.abc import Generator
import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

TEST_CREDIT_PRODUCTS = (
    '[{"product_id":"pdt_test","credits":200,"price_inr":20,"name":"200 Credits"}]'
)

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("SQS_AI_NOTE_QUEUE_URL", "test-queue-url")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test-aws-key")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test-aws-secret")
os.environ.setdefault("DODO_PAYMENTS_API_KEY", "test-dodo-key")
os.environ.setdefault("DODO_PAYMENTS_WEBHOOK_KEY", "test-dodo-webhook")
os.environ.setdefault("DODO_PAYMENTS_ENVIRONMENT", "test_mode")
os.environ.setdefault("DODO_PAYMENTS_RETURN_URL", "https://example.com/return")
os.environ.setdefault("DODO_CREDIT_PRODUCTS", TEST_CREDIT_PRODUCTS)

from src.auth import models as auth_models  # noqa: E402,F401
from src.auth import service as auth_service  # noqa: E402
from src.conversations import models as conversation_models  # noqa: E402,F401
from src.conversations import service as conversations_service  # noqa: E402
from src.credits import models as credits_models  # noqa: E402,F401
from src.internal import models as internal_models  # noqa: E402,F401
from src.internal import service as internal_service  # noqa: E402
from src.notes import models as notes_models  # noqa: E402,F401
from src.notes import service as notes_service  # noqa: E402
from src.payments import models as payments_models  # noqa: E402,F401
from src.videos import models as video_models  # noqa: E402,F401
from src import database  # noqa: E402
from src.database import Base, get_db  # noqa: E402
from src.main import create_app  # noqa: E402
from src.config import settings  # noqa: E402


TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"


def setup_settings() -> None:
    settings.secret_key = "test-secret"
    settings.jwt_expiry_hours = 1
    settings.google_client_id = "test-google-client-id"
    settings.admin_token = "test-admin-token"
    settings.db_url = TEST_DATABASE_URL
    settings.rate_limit_enabled = False
    settings.sqs_ai_note_queue_url = "test-queue-url"
    settings.aws_access_key_id = "test-aws-key"
    settings.aws_secret_access_key = "test-aws-secret"
    settings.dodo_payments_api_key = "test-dodo-key"
    settings.dodo_payments_webhook_key = "test-dodo-webhook"
    settings.dodo_payments_environment = "test_mode"
    settings.dodo_payments_return_url = "https://example.com/return"
    settings.dodo_credit_products = [
        {
            "product_id": "pdt_test",
            "credits": 200,
            "price_inr": 20,
            "name": "200 Credits",
        }
    ]
    conversations_service.conversations_settings.openrouter_api_key = (
        "test-openrouter-key"
    )


@pytest.fixture(autouse=True)
def mock_external_services(monkeypatch):
    class FakeS3Client:
        def get_object(self, *_args, **_kwargs):
            from io import BytesIO

            return {"Body": BytesIO(b"[]")}

        def put_object(self, *_args, **_kwargs):
            return {}

    class FakeSqsClient:
        def send_message(self, *_args, **_kwargs):
            return {}

    class FakeGenericClient:
        def __getattr__(self, _name):
            def _noop(*_args, **_kwargs):
                return {}

            return _noop

    def fake_boto3_client(service_name, *_args, **_kwargs):
        if service_name == "s3":
            return FakeS3Client()
        if service_name == "sqs":
            return FakeSqsClient()
        return FakeGenericClient()

    def blocked_client(*_args, **_kwargs):
        raise AssertionError("External service calls are blocked in tests.")

    monkeypatch.setattr(conversations_service.boto3, "client", fake_boto3_client)
    monkeypatch.setattr(internal_service.boto3, "client", fake_boto3_client)
    monkeypatch.setattr(notes_service.boto3, "client", fake_boto3_client)
    monkeypatch.setattr(conversations_service, "OpenAI", blocked_client)
    monkeypatch.setattr(auth_service, "verify_google_token", blocked_client)


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    database.engine = engine
    database.SessionLocal = sessionmaker(
        bind=engine,
        autocommit=False,
        autoflush=False,
    )
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(engine) -> Generator:
    connection = engine.connect()
    transaction = connection.begin()
    TestingSessionLocal = sessionmaker(
        bind=connection,
        autocommit=False,
        autoflush=False,
    )
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def app(db_session):
    setup_settings()
    app = create_app()
    from src.shared.ratelimit import limiter

    limiter.enabled = settings.rate_limit_enabled

    def get_db_override() -> Generator:
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = get_db_override
    return app


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
