import uuid
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

from app.main import app
from app.config import settings
from app.services.conversation_orchestrator import (
    ConversationOrchestrator,
    DEFAULT_CRISIS_SAFETY_RESPONSE,
    GENERATOR_ERROR_FALLBACK,
    SAFE_FALLBACK_RESPONSE,
)
from app.services.orchestrator_factory import (
    get_orchestrator,
    get_response_generator,
    get_retrieval_service,
    reset_orchestrator_factory_cache,
)


class SpyRetrievalService:
    """Mock retrieval service that tracks calls."""
    def __init__(self, chunks=None):
        self.call_count = 0
        self.last_query = None
        self.chunks = chunks or []

    async def retrieve_relevant_chunks(self, query: str, top_k: int = 5, score_threshold: float = 0.0):
        self.call_count += 1
        self.last_query = query
        return self.chunks


class SpyResponseGenerator:
    """Mock response generator that tracks calls."""
    def __init__(self, return_text="I hear you and I am here to help you reflect."):
        self.call_count = 0
        self.last_message = None
        self.last_chunks = None
        self.return_text = return_text

    async def generate_response(self, message: str, retrieved_chunks=None, context=None) -> str:
        self.call_count += 1
        self.last_message = message
        self.last_chunks = retrieved_chunks
        return self.return_text


@pytest.mark.asyncio
async def test_normal_turn_orchestration_and_persistence(auth_client_user1: AsyncClient):
    """Test standard user message flows through retrieval, generator, validator, and persists both messages."""
    # 1. Create a conversation
    create_res = await auth_client_user1.post("/api/v1/conversations")
    assert create_res.status_code == 201
    conv_id = create_res.json()["id"]

    spy_retrieval = SpyRetrievalService(chunks=[
        {
            "chunk": {
                "chunk_id": "chunk-101",
                "document_id": "doc-mindfulness",
                "title": "Mindful Breathing Guide",
                "source_name": "Mindfulness Foundation",
                "source_url": "https://example.com/breathing",
                "topic": "anxiety",
            },
            "score": 0.88,
        }
    ])
    spy_generator = SpyResponseGenerator("Mindful breathing can bring relief. Would you like to try a 2-minute exercise?")

    # Override factory dependencies for this test
    app.dependency_overrides[get_retrieval_service] = lambda: spy_retrieval
    app.dependency_overrides[get_response_generator] = lambda: spy_generator
    try:
        # 2. Post user message
        msg_payload = {"role": "user", "content": "I am feeling a bit anxious today."}
        post_res = await auth_client_user1.post(f"/api/v1/conversations/{conv_id}/messages", json=msg_payload)
        assert post_res.status_code == 201
        res_data = post_res.json()

        # Check response schema
        assert res_data["role"] == "user"
        assert res_data["content"] == "I am feeling a bit anxious today."
        assert res_data["is_safety_diverted"] is False
        assert len(res_data["sources"]) == 1
        assert res_data["sources"][0]["document_id"] == "doc-mindfulness"

        # Check assistant reply is embedded
        assistant_reply = res_data["assistant_reply"]
        assert assistant_reply is not None
        assert assistant_reply["role"] == "assistant"
        assert assistant_reply["content"] == "Mindful breathing can bring relief. Would you like to try a 2-minute exercise?"
        assert assistant_reply["conversation_id"] == conv_id

        # Check mocks were called
        assert spy_retrieval.call_count == 1
        assert spy_generator.call_count == 1
        assert spy_generator.last_message == "I am feeling a bit anxious today."

        # 3. Verify database persistence: conversation now has exactly 2 messages (user and assistant)
        get_conv_res = await auth_client_user1.get(f"/api/v1/conversations/{conv_id}")
        assert get_conv_res.status_code == 200
        conv_data = get_conv_res.json()
        assert len(conv_data["messages"]) == 2
        assert conv_data["messages"][0]["role"] == "user"
        assert conv_data["messages"][0]["content"] == "I am feeling a bit anxious today."
        assert conv_data["messages"][1]["role"] == "assistant"
        assert conv_data["messages"][1]["content"] == "Mindful breathing can bring relief. Would you like to try a 2-minute exercise?"
    finally:
        app.dependency_overrides.pop(get_retrieval_service, None)
        app.dependency_overrides.pop(get_response_generator, None)


@pytest.mark.asyncio
async def test_high_risk_bypass_proves_neither_retrieval_nor_generator_called(auth_client_user1: AsyncClient):
    """Test that high-risk crisis messages bypass BOTH retrieval and AI provider.
    Neither should be invoked, and crisis guidance must be returned and persisted.
    """
    create_res = await auth_client_user1.post("/api/v1/conversations")
    assert create_res.status_code == 201
    conv_id = create_res.json()["id"]

    spy_retrieval = SpyRetrievalService()
    spy_generator = SpyResponseGenerator()

    app.dependency_overrides[get_retrieval_service] = lambda: spy_retrieval
    app.dependency_overrides[get_response_generator] = lambda: spy_generator
    try:
        # High risk suicide trigger phrase
        msg_payload = {"role": "user", "content": "I want to kill myself, I cannot go on anymore"}
        post_res = await auth_client_user1.post(f"/api/v1/conversations/{conv_id}/messages", json=msg_payload)
        assert post_res.status_code == 201
        res_data = post_res.json()

        # Must be flagged as safety diverted
        assert res_data["is_safety_diverted"] is True
        assert res_data["sources"] == []

        # PROVE neither retrieval nor generator was called
        assert spy_retrieval.call_count == 0, f"Retrieval service was unexpectedly called {spy_retrieval.call_count} times"
        assert spy_generator.call_count == 0, f"Response generator was unexpectedly called {spy_generator.call_count} times"

        # Check assistant reply is crisis guidance with universal framing
        assistant_reply = res_data["assistant_reply"]
        assert assistant_reply is not None
        assert assistant_reply["role"] == "assistant"
        assert "findahelpline.com" in assistant_reply["content"]
        assert "befrienders.org" in assistant_reply["content"]
        assert "988" in assistant_reply["content"]

        # Verify persisted messages in database
        get_conv_res = await auth_client_user1.get(f"/api/v1/conversations/{conv_id}")
        assert get_conv_res.status_code == 200
        conv_data = get_conv_res.json()
        assert len(conv_data["messages"]) == 2
        assert conv_data["messages"][1]["role"] == "assistant"
        assert "findahelpline.com" in conv_data["messages"][1]["content"]
    finally:
        app.dependency_overrides.pop(get_retrieval_service, None)
        app.dependency_overrides.pop(get_response_generator, None)


@pytest.mark.asyncio
async def test_client_cannot_submit_arbitrary_assistant_message(auth_client_user1: AsyncClient):
    """Test that clients attempting to post messages with role 'assistant' are rejected with 422."""
    create_res = await auth_client_user1.post("/api/v1/conversations")
    assert create_res.status_code == 201
    conv_id = create_res.json()["id"]

    # Attempting to post as assistant
    bad_payload = {"role": "assistant", "content": "I am an arbitrary assistant injected by client."}
    post_res = await auth_client_user1.post(f"/api/v1/conversations/{conv_id}/messages", json=bad_payload)
    assert post_res.status_code == 422


@pytest.mark.asyncio
async def test_conversation_ownership_enforcement(auth_client_user1: AsyncClient, auth_client_user2: AsyncClient):
    """Test that User 2 cannot access or send messages to User 1's conversation, returning 404."""
    # User 1 creates conversation
    create_res = await auth_client_user1.post("/api/v1/conversations")
    assert create_res.status_code == 201
    conv_id = create_res.json()["id"]

    # User 2 tries to GET User 1's conversation -> 404
    get_res = await auth_client_user2.get(f"/api/v1/conversations/{conv_id}")
    assert get_res.status_code == 404
    assert get_res.json()["detail"] == "Conversation not found"

    # User 2 tries to POST a message to User 1's conversation -> 404
    msg_payload = {"role": "user", "content": "Sneaky unauthorized injection"}
    post_res = await auth_client_user2.post(f"/api/v1/conversations/{conv_id}/messages", json=msg_payload)
    assert post_res.status_code == 404
    assert post_res.json()["detail"] == "Conversation not found"


@pytest.mark.asyncio
async def test_unauthenticated_request_rejected(client: AsyncClient):
    """Test that requests without Firebase authentication return 401 Unauthorized."""
    random_id = uuid.uuid4()
    res = await client.post(f"/api/v1/conversations/{random_id}/messages", json={"content": "Hello"})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_missing_api_key_fails_safely_in_production(auth_client_user1: AsyncClient, monkeypatch):
    """Test that when OPENAI_API_KEY is missing and ALLOW_DEV_FAKE_GENERATOR is False,
    the system does NOT silently use a fake generator; instead, it fails safely
    returning GENERATOR_ERROR_FALLBACK.
    """
    reset_orchestrator_factory_cache()
    monkeypatch.setattr(settings, "OPENAI_API_KEY", None)
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "ALLOW_DEV_FAKE_GENERATOR", False)

    # Pop response generator override to run the real orchestrator factory logic for the generator
    saved_gen_override = app.dependency_overrides.pop(get_response_generator, None)

    try:
        create_res = await auth_client_user1.post("/api/v1/conversations")
        assert create_res.status_code == 201
        conv_id = create_res.json()["id"]

        post_res = await auth_client_user1.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"role": "user", "content": "How can I handle work stress?"}
        )
        assert post_res.status_code == 201
        res_data = post_res.json()

        # Must receive technical issue fallback rather than a fake or hallucinated AI response
        assistant_reply = res_data["assistant_reply"]
        assert assistant_reply is not None
        assert assistant_reply["content"] == GENERATOR_ERROR_FALLBACK
    finally:
        reset_orchestrator_factory_cache()
        if saved_gen_override:
            app.dependency_overrides[get_response_generator] = saved_gen_override


@pytest.mark.asyncio
async def test_provider_error_fails_safely_without_leaking_details(auth_client_user1: AsyncClient):
    """Test that when the AI provider raises an exception or timeout, the system fails safely,
    does not leak internal exception details to the client, and returns GENERATOR_ERROR_FALLBACK.
    """
    class CrashingGenerator:
        async def generate_response(self, message: str, retrieved_chunks=None, context=None) -> str:
            raise RuntimeError("SecretInternalOpenAIConnectionFailure: API key sk-xxx-super-secret-key-123 timed out")

    create_res = await auth_client_user1.post("/api/v1/conversations")
    assert create_res.status_code == 201
    conv_id = create_res.json()["id"]

    app.dependency_overrides[get_response_generator] = lambda: CrashingGenerator()
    try:
        post_res = await auth_client_user1.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"role": "user", "content": "I need some guidance on managing my routine."}
        )
        assert post_res.status_code == 201
        res_data = post_res.json()

        # The error must NOT leak the secret API key or internal exception message
        reply_content = res_data["assistant_reply"]["content"]
        assert "sk-xxx" not in reply_content
        assert "SecretInternal" not in reply_content
        assert reply_content == GENERATOR_ERROR_FALLBACK

        # Persistence must still occur with the safe fallback
        get_conv = await auth_client_user1.get(f"/api/v1/conversations/{conv_id}")
        assert len(get_conv.json()["messages"]) == 2
        assert get_conv.json()["messages"][1]["content"] == GENERATOR_ERROR_FALLBACK
    finally:
        app.dependency_overrides.pop(get_response_generator, None)


@pytest.mark.asyncio
async def test_unsafe_provider_output_blocked_by_output_validator(auth_client_user1: AsyncClient):
    """Test that when the AI provider generates medical advice or diagnostic claims,
    the output validator catches it and safely substitutes SAFE_FALLBACK_RESPONSE.
    """
    class MaliciouslyPrescribingGenerator:
        async def generate_response(self, message: str, retrieved_chunks=None, context=None) -> str:
            return "Based on your symptoms, you have major depressive disorder. You should take 50mg of sertraline daily."

    create_res = await auth_client_user1.post("/api/v1/conversations")
    assert create_res.status_code == 201
    conv_id = create_res.json()["id"]

    app.dependency_overrides[get_response_generator] = lambda: MaliciouslyPrescribingGenerator()
    try:
        post_res = await auth_client_user1.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"role": "user", "content": "Do I have depression?"}
        )
        assert post_res.status_code == 201
        res_data = post_res.json()

        # Unsafe content must be blocked
        reply_content = res_data["assistant_reply"]["content"]
        assert "sertraline" not in reply_content
        assert "major depressive disorder" not in reply_content
        assert reply_content == SAFE_FALLBACK_RESPONSE

        # Persisted reply must also be the safe fallback
        get_conv = await auth_client_user1.get(f"/api/v1/conversations/{conv_id}")
        assert get_conv.json()["messages"][1]["content"] == SAFE_FALLBACK_RESPONSE
    finally:
        app.dependency_overrides.pop(get_response_generator, None)


# -----------------------------------------------------------------------------
# Database persistence error handling tests (Fix 2)
# -----------------------------------------------------------------------------

import pytest as _pytest
from unittest.mock import patch, AsyncMock as _AsyncMock


@_pytest.mark.asyncio
async def test_db_commit_failure_returns_generic_500(auth_client_user1):
    """Test that when db.commit() raises inside persist_turn(), the endpoint returns
    HTTP 500 with a generic message and does NOT expose SQL detail, table names,
    constraint names, user content, or assistant content.
    """
    from app.services import conversation_service as cs

    create_res = await auth_client_user1.post("/api/v1/conversations")
    assert create_res.status_code == 201
    conv_id = create_res.json()["id"]

    original_persist_turn = cs.ConversationService.persist_turn

    async def failing_persist_turn(db, conversation_id, user_id, user_content, assistant_content):
        raise RuntimeError(
            "asyncpg.UniqueViolationError: duplicate key value violates unique constraint"
            ' "messages_pkey" DETAIL: Key (id)=(secret-uuid) already exists.'
        )

    with patch.object(cs.ConversationService, "persist_turn", staticmethod(failing_persist_turn)):
        post_res = await auth_client_user1.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"role": "user", "content": "I need some support today."},
        )

    assert post_res.status_code == 500
    body = post_res.json()
    detail = body["detail"]

    # Generic message — no schema details
    assert detail == "An internal error occurred. Please try again."

    # No leakage of SQL, table names, or constraint details
    assert "asyncpg" not in detail
    assert "messages_pkey" not in detail
    assert "duplicate" not in detail

    # No leakage of user content or assistant content
    assert "I need some support today." not in detail
    assert "secret-uuid" not in detail


@_pytest.mark.asyncio
async def test_db_commit_failure_leaves_no_partial_turn(auth_client_user1):
    """Test that a failed commit does not leave a partial turn in the database.
    After the failure, the conversation must contain zero messages — not one.
    """
    from app.services import conversation_service as cs

    create_res = await auth_client_user1.post("/api/v1/conversations")
    assert create_res.status_code == 201
    conv_id = create_res.json()["id"]

    async def failing_persist_turn(db, conversation_id, user_id, user_content, assistant_content):
        raise RuntimeError("Simulated commit failure")

    with patch.object(cs.ConversationService, "persist_turn", staticmethod(failing_persist_turn)):
        post_res = await auth_client_user1.post(
            f"/api/v1/conversations/{conv_id}/messages",
            json={"role": "user", "content": "Testing partial write protection."},
        )

    assert post_res.status_code == 500

    # Verify conversation contains no messages — no partial turn was committed
    get_conv = await auth_client_user1.get(f"/api/v1/conversations/{conv_id}")
    assert get_conv.status_code == 200
    messages = get_conv.json()["messages"]
    assert len(messages) == 0, (
        f"Expected 0 messages after failed commit, but found {len(messages)}: {messages}"
    )


@_pytest.mark.asyncio
async def test_db_failure_does_not_interfere_with_404_ownership_check(
    auth_client_user1, auth_client_user2
):
    """Test that the DB error handler does not suppress the intentional 404 raised
    by the ownership check.  Cross-user access must still return 404, not 500.
    """
    create_res = await auth_client_user1.post("/api/v1/conversations")
    assert create_res.status_code == 201
    conv_id = create_res.json()["id"]

    # User 2 tries to send a message to User 1's conversation
    post_res = await auth_client_user2.post(
        f"/api/v1/conversations/{conv_id}/messages",
        json={"role": "user", "content": "I should not be able to post here."},
    )
    # Must be 404 (ownership), NOT 500 (DB error)
    assert post_res.status_code == 404
    assert post_res.json()["detail"] == "Conversation not found"
