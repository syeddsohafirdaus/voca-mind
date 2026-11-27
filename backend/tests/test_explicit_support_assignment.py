"""Explicit support request assignment validation."""

from uuid import uuid4

import pytest

from app.config import settings
from tests.test_assignments import (
    register_client,
    register_doctor,
    headers,
)

SUPPORT = "/api/v1/support"
ASSIGNMENTS = "/api/v1/assignments"
ADMIN = headers("assignment-admin")


@pytest.fixture(autouse=True)
def configure_admin(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "uid-assignment-admin",
    )


async def create_request(client, token):
    response = await client.post(
        f"{SUPPORT}/request",
        headers=headers(token),
        json={
            "source": "client",
            "consent": True,
        },
    )

    assert response.status_code == 201
    return response.json()["id"]


async def setup_case(client):
    client_id = await register_client(
        client, "explicit-client"
    )

    doctor_id, _ = await register_doctor(
        client, "explicit-doctor"
    )

    request_id = await create_request(
        client, "explicit-client"
    )

    return {
        "client_id": client_id,
        "doctor_id": doctor_id,
        "support_request_id": request_id,
    }


async def propose(client, payload):
    return await client.post(
        f"{ASSIGNMENTS}/propose",
        headers=ADMIN,
        json=payload,
    )


async def assert_no_assignment(client):
    response = await client.get(
        f"{ASSIGNMENTS}/client",
        headers=headers("explicit-client"),
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_explicit_request_linked(client):
    payload = await setup_case(client)

    response = await propose(client, payload)

    assert response.status_code == 201
    assignment = response.json()
    assert assignment["status"] == "pending"

    response = await client.get(
        f"{SUPPORT}/client",
        headers=headers("explicit-client"),
    )

    assert response.status_code == 200

    request = next(
        item for item in response.json()
        if item["id"] == payload["support_request_id"]
    )

    assert request["status"] == "assigned"
    assert request["assignment_id"] == assignment["id"]


@pytest.mark.asyncio
async def test_explicit_request_preserves_consent(client):
    payload = await setup_case(client)

    response = await propose(client, payload)
    assert response.status_code == 201

    assignment_id = response.json()["id"]

    response = await client.get(
        f"{ASSIGNMENTS}/doctor",
        headers=headers("explicit-doctor"),
    )

    assert response.status_code == 200
    assert response.json() == []

    response = await client.post(
        f"{ASSIGNMENTS}/{assignment_id}/accept",
        headers=headers("explicit-client"),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "active"

    response = await client.get(
        f"{ASSIGNMENTS}/doctor",
        headers=headers("explicit-doctor"),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == assignment_id


@pytest.mark.asyncio
async def test_cancelled_request_rejected(client):
    payload = await setup_case(client)
    request_id = payload["support_request_id"]

    response = await client.post(
        f"{SUPPORT}/{request_id}/cancel",
        headers=headers("explicit-client"),
    )

    assert response.status_code == 200

    response = await propose(client, payload)

    assert response.status_code == 409
    await assert_no_assignment(client)


@pytest.mark.asyncio
async def test_nonexistent_request_rejected(client):
    payload = await setup_case(client)

    payload["support_request_id"] = str(uuid4())

    response = await propose(client, payload)

    assert response.status_code == 409
    await assert_no_assignment(client)


@pytest.mark.asyncio
async def test_other_clients_request_rejected(client):
    payload = await setup_case(client)

    await register_client(client, "explicit-other")

    payload["support_request_id"] = await create_request(
        client, "explicit-other"
    )

    response = await propose(client, payload)

    assert response.status_code == 409
    await assert_no_assignment(client)


@pytest.mark.asyncio
async def test_already_assigned_request_rejected(client):
    payload = await setup_case(client)

    first = await propose(client, payload)
    assert first.status_code == 201

    second = await propose(client, payload)
    assert second.status_code == 409

    response = await client.get(
        f"{ASSIGNMENTS}/client",
        headers=headers("explicit-client"),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == first.json()["id"]


@pytest.mark.asyncio
async def test_stale_request_cannot_replace_new_request(client):
    payload = await setup_case(client)
    old_id = payload["support_request_id"]

    response = await client.post(
        f"{SUPPORT}/{old_id}/cancel",
        headers=headers("explicit-client"),
    )

    assert response.status_code == 200

    new_id = await create_request(
        client, "explicit-client"
    )

    assert new_id != old_id

    response = await propose(client, payload)
    assert response.status_code == 409

    await assert_no_assignment(client)

    payload["support_request_id"] = new_id

    response = await propose(client, payload)
    assert response.status_code == 201


@pytest.mark.asyncio
async def test_non_admin_cannot_process_request(client):
    payload = await setup_case(client)

    response = await client.post(
        f"{ASSIGNMENTS}/propose",
        headers=headers("explicit-client"),
        json=payload,
    )

    assert response.status_code == 403
    await assert_no_assignment(client)
