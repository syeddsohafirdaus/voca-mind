from typing import AsyncGenerator
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import get_db
from app.main import app
from app.models.base import Base

# In-memory SQLite async engine for isolated testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    future=True,
)

TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    """Create all database tables before each test and drop them afterwards."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency override providing an isolated test database session."""
    async with TestAsyncSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


def mock_verify_firebase_id_token(token: str) -> dict:
    """Mock Firebase ID token verification for test environment.
    
    Tokens starting with 'invalid' or containing 'malformed' raise ValueError.
    Valid test tokens (e.g. 'token-user-1') return a dictionary containing {'uid': token_uid}.
    """
    if not token or token.startswith("invalid") or "malformed" in token:
        raise ValueError("Invalid or fake test token")
    
    # Return mock decoded claims containing uid
    uid = token if token.startswith("uid-") else f"uid-{token}"
    return {"uid": uid}


@pytest_asyncio.fixture(autouse=True)
def setup_mock_firebase_auth(monkeypatch):
    """Automatically patch verify_firebase_id_token across all tests."""
    monkeypatch.setattr("app.auth.dependencies.verify_firebase_id_token", mock_verify_firebase_id_token)


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client fixture configured for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client_user1() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client pre-configured with Bearer token for User 1."""
    transport = ASGITransport(app=app)
    headers = {"Authorization": "Bearer user-1-token"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client_user2() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client pre-configured with Bearer token for User 2."""
    transport = ASGITransport(app=app)
    headers = {"Authorization": "Bearer user-2-token"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
        yield ac
