"""Support request lifecycle, consent and privacy tests."""

import pytest

from app.config import settings

from tests.test_assignments import (
    register_client,
    register_doctor,
    ADMIN,
    CLIENT,
    DOCTOR,
    OTHER,
    BASE,
)


SUPPORT = "/api/v1/support"


@pytest.fixture(autouse=True)
def configure_admin(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "uid-assignment-admin",
    )


async def create_request(client, source="client"):
    await register_client(client, "assignment-client")

    response = await client.post(
        f"{SUPPORT}/request",
        headers=CLIENT,
        json={
            "source": source,
            "consent": True,
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"

    return response.json()


async def propose_professional(client, support):
    doctor_id, _ = await register_doctor(
        client, "assignment-doctor"
    )

    response = await client.post(
        f"{BASE}/propose",
        headers=ADMIN,
        json={
            "client_id": support["client_id"],
            "doctor_id": doctor_id,
        },
    )

    assert response.status_code == 201

    return response.json()["id"]


async def get_client_requests(client):
    response = await client.get(
        f"{SUPPORT}/client",
        headers=CLIENT,
    )

    assert response.status_code == 200

    return response.json()


@pytest.mark.asyncio
async def test_client_creates_support_request(client):
    support = await create_request(client)

    assert support["consented_at"] is not None
    assert support["assignment_id"] is None
    assert support["ended_at"] is None
    assert support["source"] == "client"


@pytest.mark.asyncio
async def test_ai_suggestion_support_request(client):
    support = await create_request(
        client, source="ai_suggestion"
    )

    assert support["source"] == "ai_suggestion"
    assert support["status"] == "pending"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"consent": False},
        {},
        {"consent": True, "source": "invalid"},
        {"consent": True, "client_id": "spoofed"},
    ],
)
async def test_invalid_consent_or_payload(client, payload):
    await register_client(client, "assignment-client")

    response = await client.post(
        f"{SUPPORT}/request",
        headers=CLIENT,
        json=payload,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unauthenticated_request_blocked(client):
    response = await client.post(
        f"{SUPPORT}/request",
        json={"consent": True},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_duplicate_request_blocked(client):
    await create_request(client)

    response = await client.post(
        f"{SUPPORT}/request",
        headers=CLIENT,
        json={"consent": True},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_client_request_history(client):
    support = await create_request(client)

    requests = await get_client_requests(client)

    assert len(requests) == 1
    assert requests[0]["id"] == support["id"]


@pytest.mark.asyncio
async def test_other_client_cannot_view_or_cancel(client):
    support = await create_request(client)

    await register_client(client, "other-client")

    response = await client.get(
        f"{SUPPORT}/client",
        headers=OTHER,
    )

    assert response.status_code == 200
    assert response.json() == []

    response = await client.post(
        f"{SUPPORT}/{support['id']}/cancel",
        headers=OTHER,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_can_view_pending_queue(client):
    support = await create_request(client)

    response = await client.get(
        f"{SUPPORT}/admin",
        headers=ADMIN,
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == support["id"]


@pytest.mark.asyncio
async def test_client_cannot_access_admin_queue(client):
    await create_request(client)

    response = await client.get(
        f"{SUPPORT}/admin",
        headers=CLIENT,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_doctor_cannot_create_client_request(client):
    await register_doctor(client, "assignment-doctor")

    response = await client.post(
        f"{SUPPORT}/request",
        headers=DOCTOR,
        json={"consent": True},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_guardian_cannot_access_support_requests(client):
    await create_request(client)

    guardian = {
        "Authorization": "Bearer support-guardian"
    }

    response = await client.post(
        "/api/v1/auth/register/guardian",
        headers=guardian,
        json={"display_name": "Synthetic Guardian"},
    )

    assert response.status_code == 201

    response = await client.get(
        f"{SUPPORT}/client",
        headers=guardian,
    )

    assert response.status_code == 403

    response = await client.post(
        f"{SUPPORT}/request",
        headers=guardian,
        json={"consent": True},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_pending_request_cancellation(client):
    support = await create_request(client)

    response = await client.post(
        f"{SUPPORT}/{support['id']}/cancel",
        headers=CLIENT,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["ended_at"] is not None


@pytest.mark.asyncio
async def test_new_request_after_cancellation(client):
    support = await create_request(client)

    response = await client.post(
        f"{SUPPORT}/{support['id']}/cancel",
        headers=CLIENT,
    )

    assert response.status_code == 200

    response = await client.post(
        f"{SUPPORT}/request",
        headers=CLIENT,
        json={"consent": True},
    )

    assert response.status_code == 201
    assert response.json()["id"] != support["id"]


@pytest.mark.asyncio
async def test_assignment_links_support_request(client):
    support = await create_request(client)

    assignment_id = await propose_professional(
        client, support
    )

    requests = await get_client_requests(client)

    assert requests[0]["status"] == "assigned"
    assert requests[0]["assignment_id"] == assignment_id

    response = await client.get(
        f"{SUPPORT}/admin",
        headers=ADMIN,
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_assignment_requires_separate_client_consent(client):
    support = await create_request(client)

    assignment_id = await propose_professional(
        client, support
    )

    url = f"/api/v1/professional/{assignment_id}/messages"

    response = await client.post(
        url,
        headers=DOCTOR,
        json={"content": "Synthetic test message."},
    )

    assert response.status_code == 403

    response = await client.post(
        f"{BASE}/{assignment_id}/accept",
        headers=CLIENT,
    )

    assert response.status_code == 200

    response = await client.post(
        url,
        headers=DOCTOR,
        json={"content": "Synthetic test message."},
    )

    assert response.status_code == 201


@pytest.mark.asyncio
async def test_request_blocked_during_assignment(client):
    support = await create_request(client)

    await propose_professional(client, support)

    response = await client.post(
        f"{SUPPORT}/request",
        headers=CLIENT,
        json={"consent": True},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_revocation_cancels_support_request(client):
    support = await create_request(client)

    assignment_id = await propose_professional(
        client, support
    )

    response = await client.post(
        f"{BASE}/{assignment_id}/accept",
        headers=CLIENT,
    )

    assert response.status_code == 200

    response = await client.post(
        f"{BASE}/{assignment_id}/revoke",
        headers=CLIENT,
    )

    assert response.status_code == 200

    requests = await get_client_requests(client)

    assert requests[0]["status"] == "cancelled"
    assert requests[0]["ended_at"] is not None


@pytest.mark.asyncio
async def test_declining_assignment_cancels_request(client):
    support = await create_request(client)

    assignment_id = await propose_professional(
        client, support
    )

    response = await client.post(
        f"{BASE}/{assignment_id}/revoke",
        headers=CLIENT,
    )

    assert response.status_code == 200

    requests = await get_client_requests(client)

    assert requests[0]["status"] == "cancelled"


@pytest.mark.asyncio
async def test_completion_closes_support_request(client):
    support = await create_request(client)

    assignment_id = await propose_professional(
        client, support
    )

    response = await client.post(
        f"{BASE}/{assignment_id}/accept",
        headers=CLIENT,
    )

    assert response.status_code == 200

    response = await client.post(
        f"{BASE}/{assignment_id}/complete",
        headers=DOCTOR,
    )

    assert response.status_code == 200

    requests = await get_client_requests(client)

    assert requests[0]["status"] == "closed"
    assert requests[0]["ended_at"] is not None


@pytest.mark.asyncio
async def test_support_request_exposes_only_metadata(client):
    await create_request(client)

    response = await client.get(
        f"{SUPPORT}/admin",
        headers=ADMIN,
    )

    assert response.status_code == 200

    allowed_fields = {
        "id",
        "client_id",
        "assignment_id",
        "source",
        "status",
        "consented_at",
        "created_at",
        "ended_at",
    }

    assert set(response.json()[0]) == allowed_fields
