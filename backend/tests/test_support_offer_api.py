"""API integration tests for professional support offers."""

import pytest

from app.main import app
from app.services.orchestrator_factory import (
    get_retrieval_service,
    get_response_generator,
)

from tests.test_endpoint_orchestration import (
    SpyRetrievalService,
    SpyResponseGenerator,
    CRISIS_FOLLOWUP_RESPONSE,
)

SUPPORT = "/api/v1/support"


@pytest.fixture
def support_spies():
    saved = dict(app.dependency_overrides)

    retrieval = SpyRetrievalService()
    generator = SpyResponseGenerator()

    app.dependency_overrides[get_retrieval_service] = (
        lambda: retrieval
    )
    app.dependency_overrides[get_response_generator] = (
        lambda: generator
    )

    try:
        yield retrieval, generator
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(saved)


async def create_conversation(client):
    response = await client.post("/api/v1/conversations")
    assert response.status_code == 201
    return response.json()["id"]


async def send_message(client, conversation_id, content):
    response = await client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"role": "user", "content": content},
    )
    assert response.status_code == 201
    return response.json()


async def get_support_requests(client):
    response = await client.get(f"{SUPPORT}/client")
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_normal_conversation_has_no_offer(
    auth_client_user1, support_spies
):
    cid = await create_conversation(auth_client_user1)

    data = await send_message(
        auth_client_user1, cid,
        "I have many college assignments today."
    )

    assert data["support_offer"]["offered"] is False
    assert data["support_offer"]["priority"] == "none"
    assert data["is_safety_diverted"] is False


@pytest.mark.asyncio
async def test_crisis_returns_professional_offer(
    auth_client_user1, support_spies
):
    cid = await create_conversation(auth_client_user1)

    data = await send_message(
        auth_client_user1, cid, "I want to die."
    )

    offer = data["support_offer"]

    assert offer["offered"] is True
    assert offer["priority"] == "urgent"
    assert offer["requires_consent"] is True
    assert offer["automatic_notification"] is False
    assert offer["emergency_service"] is False


@pytest.mark.asyncio
async def test_crisis_offer_preserves_safety_guidance(
    auth_client_user1, support_spies
):
    retrieval, generator = support_spies
    cid = await create_conversation(auth_client_user1)

    data = await send_message(
        auth_client_user1, cid, "I want to die."
    )

    assert data["is_safety_diverted"] is True
    assert data["sources"] == []
    assert retrieval.call_count == 0
    assert generator.call_count == 0

    reply = data["assistant_reply"]["content"]

    assert "112" in reply
    assert "14416" in reply
    assert "findahelpline.com" in reply


@pytest.mark.asyncio
async def test_offer_does_not_create_support_request(
    auth_client_user1, support_spies
):
    cid = await create_conversation(auth_client_user1)

    data = await send_message(
        auth_client_user1, cid, "I want to die."
    )

    assert data["support_offer"]["offered"] is True
    assert await get_support_requests(auth_client_user1) == []


@pytest.mark.asyncio
async def test_client_can_explicitly_accept_offer(
    auth_client_user1, support_spies
):
    cid = await create_conversation(auth_client_user1)

    data = await send_message(
        auth_client_user1, cid, "I want to die."
    )

    assert data["support_offer"]["offered"] is True

    response = await auth_client_user1.post(
        f"{SUPPORT}/request",
        json={"source": "ai_suggestion", "consent": True},
    )

    assert response.status_code == 201

    request = response.json()

    assert request["source"] == "ai_suggestion"
    assert request["status"] == "pending"
    assert request["assignment_id"] is None
    assert request["consented_at"] is not None


@pytest.mark.asyncio
async def test_declined_consent_creates_no_request(
    auth_client_user1, support_spies
):
    cid = await create_conversation(auth_client_user1)

    await send_message(
        auth_client_user1, cid, "I want to die."
    )

    response = await auth_client_user1.post(
        f"{SUPPORT}/request",
        json={"source": "ai_suggestion", "consent": False},
    )

    assert response.status_code == 422
    assert await get_support_requests(auth_client_user1) == []


@pytest.mark.asyncio
async def test_crisis_followup_retains_support_offer(
    auth_client_user1, support_spies
):
    cid = await create_conversation(auth_client_user1)

    await send_message(
        auth_client_user1, cid, "I want to die."
    )

    followup = await send_message(
        auth_client_user1, cid, "I don't know what to do."
    )

    assert followup["is_safety_diverted"] is True
    assert followup["support_offer"]["offered"] is True
    assert (
        followup["assistant_reply"]["content"]
        == CRISIS_FOLLOWUP_RESPONSE
    )


@pytest.mark.asyncio
async def test_other_client_cannot_access_offer(
    auth_client_user1, auth_client_user2, support_spies
):
    cid = await create_conversation(auth_client_user1)

    response = await auth_client_user2.post(
        f"/api/v1/conversations/{cid}/messages",
        json={"role": "user", "content": "Hello."},
    )

    assert response.status_code == 404
    assert "support_offer" not in response.json()


@pytest.mark.asyncio
async def test_offer_contains_no_private_identifiers(
    auth_client_user1, support_spies
):
    cid = await create_conversation(auth_client_user1)

    data = await send_message(
        auth_client_user1, cid, "I want to die."
    )

    forbidden_fields = {
        "client_id",
        "conversation_id",
        "user_id",
        "doctor_id",
        "firebase_uid",
        "conversation_history",
        "reasons",
        "confidence",
    }

    assert not forbidden_fields.intersection(
        data["support_offer"]
    )


@pytest.mark.asyncio
async def test_duplicate_support_request_blocked(
    auth_client_user1, support_spies
):
    cid = await create_conversation(auth_client_user1)

    await send_message(
        auth_client_user1, cid, "I want to die."
    )

    payload = {
        "source": "ai_suggestion",
        "consent": True,
    }

    first = await auth_client_user1.post(
        f"{SUPPORT}/request", json=payload
    )

    assert first.status_code == 201

    second = await auth_client_user1.post(
        f"{SUPPORT}/request", json=payload
    )

    assert second.status_code == 409

    requests = await get_support_requests(
        auth_client_user1
    )

    assert len(requests) == 1


@pytest.mark.asyncio
async def test_pending_request_suppresses_offer(
    auth_client_user1, support_spies
):
    response = await auth_client_user1.post(
        f"{SUPPORT}/request",
        json={"source": "client", "consent": True},
    )

    assert response.status_code == 201

    cid = await create_conversation(auth_client_user1)

    data = await send_message(
        auth_client_user1, cid, "I want to die."
    )

    assert data["support_offer"]["offered"] is False
    assert data["support_offer"]["action"] is None
    assert data["support_offer"]["priority"] == "none"


@pytest.mark.asyncio
async def test_suppression_preserves_crisis_guidance(
    auth_client_user1, support_spies
):
    response = await auth_client_user1.post(
        f"{SUPPORT}/request",
        json={"source": "client", "consent": True},
    )

    assert response.status_code == 201

    cid = await create_conversation(auth_client_user1)

    data = await send_message(
        auth_client_user1, cid, "I want to die."
    )

    assert data["support_offer"]["offered"] is False
    assert data["is_safety_diverted"] is True

    reply = data["assistant_reply"]["content"]

    assert "112" in reply
    assert "14416" in reply
    assert "findahelpline.com" in reply


@pytest.mark.asyncio
async def test_cancelled_request_allows_new_offer(
    auth_client_user1, support_spies
):
    response = await auth_client_user1.post(
        f"{SUPPORT}/request",
        json={"source": "client", "consent": True},
    )

    assert response.status_code == 201

    request_id = response.json()["id"]

    cancelled = await auth_client_user1.post(
        f"{SUPPORT}/{request_id}/cancel"
    )

    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    cid = await create_conversation(auth_client_user1)

    data = await send_message(
        auth_client_user1, cid, "I want to die."
    )

    assert data["support_offer"]["offered"] is True
    assert data["support_offer"]["priority"] == "urgent"


from tests.test_assignments import (
    setup_assignment,
    CLIENT,
    BASE,
)


@pytest.fixture
def assignment_admin(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "uid-assignment-admin",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("accept", [False, True])
async def test_open_assignment_suppresses_offer(
    client, support_spies, assignment_admin, accept
):
    assignment_id, _, _ = await setup_assignment(client)

    if accept:
        response = await client.post(
            f"{BASE}/{assignment_id}/accept",
            headers=CLIENT,
        )
        assert response.status_code == 200

    response = await client.post(
        "/api/v1/conversations",
        headers=CLIENT,
    )

    assert response.status_code == 201
    cid = response.json()["id"]

    response = await client.post(
        f"/api/v1/conversations/{cid}/messages",
        headers=CLIENT,
        json={
            "role": "user",
            "content": "I want to die.",
        },
    )

    assert response.status_code == 201
    data = response.json()

    assert data["support_offer"]["offered"] is False
    assert data["is_safety_diverted"] is True
    assert "112" in data["assistant_reply"]["content"]


@pytest.mark.asyncio
async def test_other_clients_request_does_not_suppress(
    auth_client_user1, auth_client_user2, support_spies
):
    response = await auth_client_user1.post(
        f"{SUPPORT}/request",
        json={"source": "client", "consent": True},
    )

    assert response.status_code == 201

    cid = await create_conversation(auth_client_user2)

    data = await send_message(
        auth_client_user2, cid, "I want to die."
    )

    assert data["support_offer"]["offered"] is True
    assert data["support_offer"]["priority"] == "urgent"
    assert data["is_safety_diverted"] is True

    assert await get_support_requests(
        auth_client_user2
    ) == []


@pytest.mark.asyncio
async def test_availability_failure_preserves_crisis(
    auth_client_user1, support_spies, monkeypatch
):
    async def failing_check(*args, **kwargs):
        raise RuntimeError("Simulated availability failure")

    monkeypatch.setattr(
        "app.api.conversations.has_open_professional_support",
        failing_check,
    )

    cid = await create_conversation(auth_client_user1)

    data = await send_message(
        auth_client_user1, cid, "I want to die."
    )

    assert data["support_offer"]["offered"] is True
    assert data["support_offer"]["requires_consent"] is True
    assert data["is_safety_diverted"] is True

    reply = data["assistant_reply"]["content"]

    assert "112" in reply
    assert "14416" in reply

    assert await get_support_requests(
        auth_client_user1
    ) == []
