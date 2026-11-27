"""Notification API functionality and privacy tests."""

from uuid import uuid4

import pytest

from app.config import settings

from tests.test_assignments import (
    register_client,
    register_doctor,
    headers,
)

from tests.test_notification_lifecycle import (
    setup_case,
    propose,
    accept,
    CLIENT,
    DOCTOR,
    ADMIN,
)

BASE = "/api/v1/notifications"


@pytest.fixture(autouse=True)
def configure_admin(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "uid-assignment-admin",
    )


@pytest.mark.asyncio
async def test_empty_notifications(client):
    await register_client(client, "notify-client")

    response = await client.get(BASE, headers=CLIENT)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_notification_listing(client):
    client_id, doctor_id = await setup_case(client)

    assignment_id = await propose(
        client, client_id, doctor_id
    )

    response = await client.get(BASE, headers=CLIENT)

    assert response.status_code == 200

    items = response.json()

    assert len(items) == 1
    assert items[0]["event_type"] == "assignment_proposed"
    assert items[0]["reference_id"] == assignment_id
    assert items[0]["read_at"] is None

    assert set(items[0]) == {
        "id",
        "event_type",
        "reference_id",
        "created_at",
        "read_at",
    }


@pytest.mark.asyncio
async def test_verified_doctor_notifications(client):
    client_id, doctor_id = await setup_case(client)

    assignment_id = await propose(
        client, client_id, doctor_id
    )

    response = await client.get(BASE, headers=DOCTOR)

    assert response.status_code == 200
    assert response.json() == []

    await accept(client, assignment_id)

    response = await client.get(BASE, headers=DOCTOR)

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["event_type"] == "assignment_accepted"


@pytest.mark.asyncio
async def test_unread_count_and_mark_read(client):
    client_id, doctor_id = await setup_case(client)

    await propose(client, client_id, doctor_id)

    response = await client.get(
        f"{BASE}/unread", headers=CLIENT
    )

    assert response.status_code == 200
    assert response.json() == {"unread_count": 1}

    response = await client.get(BASE, headers=CLIENT)

    notification_id = response.json()[0]["id"]

    response = await client.post(
        f"{BASE}/{notification_id}/read",
        headers=CLIENT,
    )

    assert response.status_code == 200
    assert response.json()["read_at"] is not None

    response = await client.get(
        f"{BASE}/unread", headers=CLIENT
    )

    assert response.json() == {"unread_count": 0}

    response = await client.get(
        BASE, headers=CLIENT,
        params={"unread_only": True},
    )

    assert response.json() == []


@pytest.mark.asyncio
async def test_mark_read_is_idempotent(client):
    client_id, doctor_id = await setup_case(client)

    await propose(client, client_id, doctor_id)

    response = await client.get(BASE, headers=CLIENT)
    notification_id = response.json()[0]["id"]

    url = f"{BASE}/{notification_id}/read"

    first = await client.post(url, headers=CLIENT)
    second = await client.post(url, headers=CLIENT)

    assert first.status_code == 200
    assert second.status_code == 200

    assert first.json()["read_at"] is not None
    assert first.json()["read_at"] == second.json()["read_at"]

    response = await client.get(BASE, headers=CLIENT)

    assert response.json()[0]["read_at"] == first.json()["read_at"]


@pytest.mark.asyncio
async def test_cross_client_notification_isolation(client):
    client_id, doctor_id = await setup_case(client)

    await register_client(client, "notify-other")

    await propose(client, client_id, doctor_id)

    response = await client.get(BASE, headers=CLIENT)
    notification_id = response.json()[0]["id"]

    other = headers("notify-other")

    response = await client.get(BASE, headers=other)

    assert response.status_code == 200
    assert response.json() == []

    response = await client.get(
        f"{BASE}/unread", headers=other
    )

    assert response.json() == {"unread_count": 0}

    response = await client.post(
        f"{BASE}/{notification_id}/read",
        headers=other,
    )

    assert response.status_code == 404

    response = await client.get(BASE, headers=CLIENT)

    assert response.json()[0]["read_at"] is None


@pytest.mark.asyncio
async def test_missing_notification(client):
    await register_client(client, "notify-client")

    response = await client.post(
        f"{BASE}/{uuid4()}/read",
        headers=CLIENT,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", BASE),
        ("GET", f"{BASE}/unread"),
        ("POST", f"{BASE}/{uuid4()}/read"),
    ],
)
async def test_unauthenticated_access(client, method, path):
    response = await client.request(method, path)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_cannot_access_notifications(client):
    response = await client.get(BASE, headers=ADMIN)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unverified_doctor_blocked(client):
    await register_doctor(
        client, "notify-doctor", approve=False
    )

    response = await client.get(BASE, headers=DOCTOR)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_suspended_doctor_blocked(client):
    _, application_id = await register_doctor(
        client, "notify-doctor"
    )

    response = await client.post(
        f"/api/v1/admin/doctor-applications/{application_id}/suspend",
        headers=ADMIN,
        json={"reason": "Synthetic suspension test."},
    )

    assert response.status_code == 200

    response = await client.get(BASE, headers=DOCTOR)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_guardian_blocked(client):
    guardian = headers("notify-guardian")

    response = await client.post(
        "/api/v1/auth/register/guardian",
        headers=guardian,
        json={"display_name": "Synthetic Guardian"},
    )

    assert response.status_code == 201

    response = await client.get(BASE, headers=guardian)

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_notification_pagination(client):
    client_id, doctor_id = await setup_case(client)

    response = await client.post(
        "/api/v1/support/request",
        headers=CLIENT,
        json={"source": "client", "consent": True},
    )

    assert response.status_code == 201

    await propose(client, client_id, doctor_id)

    first = await client.get(
        BASE,
        headers=CLIENT,
        params={"limit": 1, "offset": 0},
    )

    second = await client.get(
        BASE,
        headers=CLIENT,
        params={"limit": 1, "offset": 1},
    )

    assert first.status_code == 200
    assert second.status_code == 200

    assert len(first.json()) == 1
    assert len(second.json()) == 1

    assert first.json()[0]["event_type"] == "assignment_proposed"
    assert second.json()[0]["event_type"] == "support_requested"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"unread_only": "invalid"},
    ],
)
async def test_invalid_query_parameters(client, params):
    await register_client(client, "notify-client")

    response = await client.get(
        BASE, headers=CLIENT, params=params
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_invalid_notification_id(client):
    await register_client(client, "notify-client")

    response = await client.post(
        f"{BASE}/invalid-id/read",
        headers=CLIENT,
    )

    assert response.status_code == 422
