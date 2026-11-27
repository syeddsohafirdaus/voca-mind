"""Human takeover API lifecycle and consent tests."""

import pytest

from app.config import settings

from tests.test_assignments import (
    setup_assignment,
    register_client,
    register_doctor,
    headers,
    CLIENT,
    DOCTOR,
    ADMIN,
    ADMIN_BASE,
)

BASE = "/api/v1/takeovers"
ASSIGNMENTS = "/api/v1/assignments"


@pytest.fixture(autouse=True)
def configure_admin(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "uid-assignment-admin",
    )


async def prepare_assignment(client):
    assignment_id, _, application_id = (
        await setup_assignment(client)
    )

    response = await client.post(
        f"{ASSIGNMENTS}/{assignment_id}/accept",
        headers=CLIENT,
    )

    assert response.status_code == 200

    return assignment_id, application_id


async def request_session(client, assignment_id):
    response = await client.post(
        f"{BASE}/{assignment_id}/request",
        headers=CLIENT,
        json={"consent": True},
    )

    assert response.status_code == 201
    return response.json()


async def accept_session(client, assignment_id, takeover_id):
    response = await client.post(
        f"{BASE}/{assignment_id}/accept?takeover_id={takeover_id}",
        headers=DOCTOR,
    )

    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_complete_takeover_lifecycle(client):
    assignment_id, _ = await prepare_assignment(client)

    requested = await request_session(
        client, assignment_id
    )

    assert requested["status"] == "requested"
    assert requested["consented_at"] is not None
    assert requested["accepted_at"] is None

    active = await accept_session(client, assignment_id, requested["id"])

    assert active["status"] == "active"
    assert active["accepted_at"] is not None

    response = await client.post(
        f"{BASE}/{assignment_id}/end?takeover_id={requested['id']}",
        headers=CLIENT,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ended"
    assert response.json()["ended_at"] is not None


@pytest.mark.asyncio
async def test_cancel_pending_takeover(client):
    assignment_id, _ = await prepare_assignment(client)

    requested = await request_session(client, assignment_id)

    response = await client.post(
        f"{BASE}/{assignment_id}/cancel?takeover_id={requested['id']}",
        headers=CLIENT,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["accepted_at"] is None
    assert response.json()["ended_at"] is not None


@pytest.mark.asyncio
async def test_doctor_can_end_takeover(client):
    assignment_id, _ = await prepare_assignment(client)

    requested = await request_session(client, assignment_id)
    await accept_session(client, assignment_id, requested["id"])

    response = await client.post(
        f"{BASE}/{assignment_id}/end?takeover_id={requested['id']}",
        headers=DOCTOR,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ended"


@pytest.mark.asyncio
async def test_duplicate_request_rejected(client):
    assignment_id, _ = await prepare_assignment(client)

    requested = await request_session(client, assignment_id)

    response = await client.post(
        f"{BASE}/{assignment_id}/request",
        headers=CLIENT,
        json={"consent": True},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_new_request_after_end(client):
    assignment_id, _ = await prepare_assignment(client)

    first = await request_session(
        client, assignment_id
    )

    await accept_session(client, assignment_id, first["id"])

    response = await client.post(
        f"{BASE}/{assignment_id}/end?takeover_id={first['id']}",
        headers=CLIENT,
    )

    assert response.status_code == 200

    second = await request_session(
        client, assignment_id
    )

    assert first["id"] != second["id"]
    assert second["status"] == "requested"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"consent": False},
        {"consent": "true"},
        {"consent": 1},
        {"consent": True, "extra": "invalid"},
    ],
)
async def test_explicit_consent_required(client, payload):
    assignment_id, _ = await prepare_assignment(client)

    response = await client.post(
        f"{BASE}/{assignment_id}/request",
        headers=CLIENT,
        json=payload,
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_pending_assignment_cannot_request(client):
    assignment_id, _, _ = await setup_assignment(client)

    response = await client.post(
        f"{BASE}/{assignment_id}/request",
        headers=CLIENT,
        json={"consent": True},
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_unauthenticated_listing(client):
    response = await client.get(f"{BASE}/client")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_client_cannot_accept_takeover(client):
    assignment_id, _ = await prepare_assignment(client)

    requested = await request_session(client, assignment_id)

    response = await client.post(
        f"{BASE}/{assignment_id}/accept?takeover_id={requested['id']}",
        headers=CLIENT,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_doctor_cannot_request_takeover(client):
    assignment_id, _ = await prepare_assignment(client)

    response = await client.post(
        f"{BASE}/{assignment_id}/request",
        headers=DOCTOR,
        json={"consent": True},
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_other_client_cannot_end_takeover(client):
    assignment_id, _ = await prepare_assignment(client)

    requested = await request_session(client, assignment_id)
    await accept_session(client, assignment_id, requested["id"])

    await register_client(client, "unrelated-client")

    response = await client.post(
        f"{BASE}/{assignment_id}/end?takeover_id={requested['id']}",
        headers=headers("unrelated-client"),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_other_doctor_cannot_accept_takeover(client):
    assignment_id, _ = await prepare_assignment(client)

    requested = await request_session(client, assignment_id)

    await register_doctor(client, "unrelated-doctor")

    response = await client.post(
        f"{BASE}/{assignment_id}/accept?takeover_id={requested['id']}",
        headers=headers("unrelated-doctor"),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_client_can_end_after_doctor_suspension(client):
    assignment_id, application_id = (
        await prepare_assignment(client)
    )

    requested = await request_session(client, assignment_id)
    await accept_session(client, assignment_id, requested["id"])

    response = await client.post(
        f"{ADMIN_BASE}/{application_id}/suspend",
        headers=ADMIN,
        json={"reason": "Synthetic suspension test."},
    )

    assert response.status_code == 200

    response = await client.post(
        f"{BASE}/{assignment_id}/end?takeover_id={requested['id']}",
        headers=CLIENT,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ended"


@pytest.mark.asyncio
async def test_session_metadata_privacy(client):
    assignment_id, _ = await prepare_assignment(client)

    requested = await request_session(client, assignment_id)

    expected_fields = {
        "id",
        "assignment_id",
        "status",
        "consented_at",
        "accepted_at",
        "ended_at",
        "created_at",
    }

    for role, auth in [
        ("client", CLIENT),
        ("doctor", DOCTOR),
    ]:
        response = await client.get(
            f"{BASE}/{role}",
            headers=auth,
        )

        assert response.status_code == 200
        assert len(response.json()) == 1
        assert set(response.json()[0]) == expected_fields


@pytest.mark.asyncio
async def test_revoked_assignment_hides_doctor_sessions(client):
    assignment_id, _ = await prepare_assignment(client)

    requested = await request_session(client, assignment_id)
    await accept_session(client, assignment_id, requested["id"])

    response = await client.post(
        f"{ASSIGNMENTS}/{assignment_id}/revoke",
        headers=CLIENT,
    )

    assert response.status_code == 200

    response = await client.get(
        f"{BASE}/doctor",
        headers=DOCTOR,
    )

    assert response.status_code == 200
    assert response.json() == []

    response = await client.get(
        f"{BASE}/client",
        headers=CLIENT,
    )

    assert response.status_code == 200
    assert response.json()[0]["status"] == "ended"


@pytest.mark.asyncio
async def test_cross_client_listing_isolation(client):
    assignment_id, _ = await prepare_assignment(client)

    requested = await request_session(client, assignment_id)

    await register_client(client, "isolated-client")

    response = await client.get(
        f"{BASE}/client",
        headers=headers("isolated-client"),
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_cross_doctor_listing_isolation(client):
    assignment_id, _ = await prepare_assignment(client)

    requested = await request_session(client, assignment_id)

    await register_doctor(client, "isolated-doctor")

    response = await client.get(
        f"{BASE}/doctor",
        headers=headers("isolated-doctor"),
    )

    assert response.status_code == 200
    assert response.json() == []
