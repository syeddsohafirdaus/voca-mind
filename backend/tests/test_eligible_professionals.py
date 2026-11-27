"""Administrator-only eligible professional directory tests."""

import pytest

from app.config import settings
from tests.test_assignments import (
    register_client,
    register_doctor,
    headers,
)

BASE = "/api/v1/admin/eligible-professionals"
ADMIN = headers("assignment-admin")


@pytest.fixture(autouse=True)
def configure_admin(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "uid-assignment-admin",
    )


@pytest.mark.asyncio
async def test_empty_directory(client):
    response = await client.get(BASE, headers=ADMIN)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_unauthenticated_directory_blocked(client):
    response = await client.get(BASE)

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_non_admin_directory_blocked(client):
    await register_client(client, "directory-client")

    response = await client.get(
        BASE,
        headers=headers("directory-client"),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_verified_professional_included(client):
    doctor_id, _ = await register_doctor(
        client, "directory-verified"
    )

    response = await client.get(BASE, headers=ADMIN)

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1
    assert data[0]["id"] == doctor_id
    assert data[0]["verified"] is True
    assert data[0]["specialization"] == "Psychiatry"


@pytest.mark.asyncio
async def test_pending_professional_excluded(client):
    await register_doctor(
        client,
        "directory-pending",
        approve=False,
    )

    response = await client.get(BASE, headers=ADMIN)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_suspended_professional_excluded(client):
    _, application_id = await register_doctor(
        client, "directory-suspended"
    )

    response = await client.post(
        f"/api/v1/admin/doctor-applications/{application_id}/suspend",
        headers=ADMIN,
        json={"reason": "Synthetic suspension test."},
    )

    assert response.status_code == 200

    response = await client.get(BASE, headers=ADMIN)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_rejected_professional_excluded(client):
    _, application_id = await register_doctor(
        client,
        "directory-rejected",
        approve=False,
    )

    response = await client.post(
        f"/api/v1/admin/doctor-applications/{application_id}/reject",
        headers=ADMIN,
        json={"reason": "Synthetic rejection test."},
    )

    assert response.status_code == 200

    response = await client.get(BASE, headers=ADMIN)

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_directory_privacy(client):
    await register_doctor(client, "directory-privacy")

    response = await client.get(BASE, headers=ADMIN)

    assert response.status_code == 200

    data = response.json()

    assert len(data) == 1

    assert set(data[0]) == {
        "id",
        "display_name",
        "specialization",
        "licensing_authority",
        "verified",
    }


@pytest.mark.asyncio
async def test_directory_pagination(client):
    await register_doctor(client, "directory-first")
    await register_doctor(client, "directory-second")

    first = await client.get(
        BASE,
        headers=ADMIN,
        params={"limit": 1, "offset": 0},
    )

    second = await client.get(
        BASE,
        headers=ADMIN,
        params={"limit": 1, "offset": 1},
    )

    assert first.status_code == 200
    assert second.status_code == 200

    assert len(first.json()) == 1
    assert len(second.json()) == 1

    assert first.json()[0]["id"] != second.json()[0]["id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("params", [
    {"limit": 0},
    {"limit": 101},
    {"offset": -1},
])
async def test_invalid_pagination(client, params):
    response = await client.get(
        BASE,
        headers=ADMIN,
        params=params,
    )

    assert response.status_code == 422
