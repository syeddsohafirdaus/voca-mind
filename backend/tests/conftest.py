import os
import tempfile

# Isolate knowledge storage before importing application modules.
_test_knowledge_storage = tempfile.TemporaryDirectory(
    prefix="voca-test-qdrant-"
)

os.environ["QDRANT_MODE"] = "local"
os.environ["QDRANT_LOCAL_PATH"] = _test_knowledge_storage.name
os.environ["QDRANT_COLLECTION_NAME"] = "voca_test_knowledge"
os.environ["QDRANT_API_KEY"] = ""
os.environ["EMBEDDING_PROVIDER"] = "fake"
os.environ["EMBEDDING_DIMENSION"] = "1536"

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


class TestFakeRetrievalService:
    async def retrieve_relevant_chunks(self, query: str, top_k: int = 5, score_threshold: float = 0.0):
        return []


from app.services.conversation_orchestrator import DeterministicFakeResponseGenerator
from app.services.orchestrator_factory import get_response_generator, get_retrieval_service

app.dependency_overrides[get_retrieval_service] = lambda: TestFakeRetrievalService()
app.dependency_overrides[get_response_generator] = lambda: DeterministicFakeResponseGenerator()


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
        response = await ac.post(
            "/api/v1/auth/register/client",
            json={
                "display_name": "Test Client 1",
                "date_of_birth": "2003-01-15",
            },
        )
        assert response.status_code == 201, response.text
        yield ac


@pytest_asyncio.fixture
async def auth_client_user2() -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client pre-configured with Bearer token for User 2."""
    transport = ASGITransport(app=app)
    headers = {"Authorization": "Bearer user-2-token"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
        response = await ac.post(
            "/api/v1/auth/register/client",
            json={
                "display_name": "Test Client 2",
                "date_of_birth": "2003-01-15",
            },
        )
        assert response.status_code == 201, response.text
        yield ac


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def cleanup_test_knowledge_storage():
    yield
    from app.knowledge.client_manager import close_local_qdrant_client
    from app.knowledge.operation_executor import (
        run_knowledge_operation,
        shutdown_knowledge_executor,
    )

    try:
        await run_knowledge_operation(
            close_local_qdrant_client
        )
    finally:
        shutdown_knowledge_executor()
        _test_knowledge_storage.cleanup()


import pytest


@pytest.fixture
def signed_test_approval(tmp_path, monkeypatch):
    import base64
    import json
    from datetime import datetime, timezone

    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )

    from app.knowledge.approval import (
        DocumentApproval,
        document_fingerprint,
        chunk_fingerprint,
    )

    from app.knowledge.secure_approval_loader import (
        load_secure_approval_registry,
    )

    private_key = Ed25519PrivateKey.generate()

    public_key = base64.b64encode(
        private_key.public_key().public_bytes_raw()
    ).decode()

    manifest = tmp_path / "approvals.json"
    signature = tmp_path / "approvals.sig"

    def configure(doc, chunks, status="APPROVED"):
        approval = DocumentApproval(
            document_id=doc.document_id,
            version=doc.version,
            fingerprint=document_fingerprint(doc),
            chunk_fingerprints=tuple(
                chunk_fingerprint(chunk)
                for chunk in chunks
            ),
            reviewer_id="synthetic-test-reviewer",
            approved_at=datetime.now(timezone.utc),
            status=status,
        )

        content = json.dumps({
            "schema_version": 1,
            "approvals": [
                approval.model_dump(mode="json")
            ],
        }).encode("utf-8")

        manifest.write_bytes(content)

        signature.write_text(
            base64.b64encode(
                private_key.sign(content)
            ).decode()
        )

        def load_registry():
            return load_secure_approval_registry(
                manifest,
                signature,
                public_key,
            )

        monkeypatch.setattr(
            "app.knowledge.ingestion.load_secure_approval_registry",
            load_registry,
        )

        monkeypatch.setattr(
            "app.knowledge.retrieval.load_secure_approval_registry",
            load_registry,
        )

        return load_registry()

    return configure
