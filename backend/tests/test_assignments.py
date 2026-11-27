"""Professional assignment and consent integration tests."""

import pytest
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.user import User


BASE = "/api/v1/assignments"
ADMIN_BASE = "/api/v1/admin/doctor-applications"


def headers(token):
    return {"Authorization": f"Bearer {token}"}


ADMIN = headers("assignment-admin")
CLIENT = headers("assignment-client")
DOCTOR = headers("assignment-doctor")
OTHER = headers("other-client")
OTHER_DOCTOR = headers("other-doctor")


@pytest.fixture(autouse=True)
def configure_admin(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "uid-assignment-admin",
    )


async def get_user_id(token):
    async for db in app.dependency_overrides[get_db]():
        result = await db.execute(
            select(User.id).where(
                User.firebase_uid == f"uid-{token}"
            )
        )
        return str(result.scalar_one())


async def register_client(client, token):
    response = await client.post(
        "/api/v1/auth/register/client",
        headers=headers(token),
        json={
            "display_name": "Synthetic Client",
            "date_of_birth": "2003-01-15",
        },
    )
    assert response.status_code == 201
    return await get_user_id(token)


async def register_doctor(client, token, approve=True):
    response = await client.post(
        "/api/v1/auth/register/doctor",
        headers=headers(token),
        json={
            "display_name": "Synthetic Doctor",
            "registration_number": f"TEST-{token}",
            "licensing_authority": "Test Authority",
            "specialization": "Psychiatry",
        },
    )
    assert response.status_code == 201

    response = await client.get(
        ADMIN_BASE, headers=ADMIN
    )
    assert response.status_code == 200

    application = next(
        item for item in response.json()
        if item["registration_number"] == f"TEST-{token}"
    )

    if approve:
        response = await client.post(
            f"{ADMIN_BASE}/{application['id']}/approve",
            headers=ADMIN,
            json={"reason": "Synthetic verification test."},
        )
        assert response.status_code == 200

    return await get_user_id(token), application["id"]


async def setup_assignment(client):
    client_id = await register_client(
        client, "assignment-client"
    )

    doctor_id, application_id = await register_doctor(
        client, "assignment-doctor"
    )

    payload = {
        "client_id": client_id,
        "doctor_id": doctor_id,
    }

    response = await client.post(
        f"{BASE}/propose",
        headers=ADMIN,
        json=payload,
    )

    assert response.status_code == 201
    assert response.json()["status"] == "pending"

    return response.json()["id"], payload, application_id


@pytest.mark.asyncio
async def test_unauthenticated_access(client):
    response = await client.get(f"{BASE}/client")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_pending_assignment_hidden_from_doctor(client):
    assignment_id, _, _ = await setup_assignment(client)

    response = await client.get(
        f"{BASE}/doctor", headers=DOCTOR
    )

    assert response.status_code == 200
    assert response.json() == []

    response = await client.get(
        f"{BASE}/client", headers=CLIENT
    )

    assert response.status_code == 200
    assert response.json()[0]["id"] == assignment_id
    assert response.json()[0]["status"] == "pending"


@pytest.mark.asyncio
async def test_client_consent_activates_assignment(client):
    assignment_id, _, _ = await setup_assignment(client)

    response = await client.post(
        f"{BASE}/{assignment_id}/accept",
        headers=CLIENT,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    assert response.json()["consented_at"] is not None

    response = await client.get(
        f"{BASE}/doctor", headers=DOCTOR
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["id"] == assignment_id


@pytest.mark.asyncio
async def test_revocation_removes_doctor_access(client):
    assignment_id, _, _ = await setup_assignment(client)

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
    assert response.json()["status"] == "revoked"
    assert response.json()["ended_at"] is not None

    response = await client.get(
        f"{BASE}/doctor", headers=DOCTOR
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_client_can_decline_assignment(client):
    assignment_id, _, _ = await setup_assignment(client)

    response = await client.post(
        f"{BASE}/{assignment_id}/revoke",
        headers=CLIENT,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "revoked"
    assert response.json()["consented_at"] is None


@pytest.mark.asyncio
async def test_duplicate_assignment_blocked(client):
    _, payload, _ = await setup_assignment(client)

    response = await client.post(
        f"{BASE}/propose",
        headers=ADMIN,
        json=payload,
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_non_admin_cannot_propose(client):
    _, payload, _ = await setup_assignment(client)

    response = await client.post(
        f"{BASE}/propose",
        headers=CLIENT,
        json=payload,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unverified_doctor_cannot_be_assigned(client):
    client_id = await register_client(
        client, "assignment-client"
    )

    doctor_id, _ = await register_doctor(
        client, "assignment-doctor", approve=False
    )

    response = await client.post(
        f"{BASE}/propose",
        headers=ADMIN,
        json={
            "client_id": client_id,
            "doctor_id": doctor_id,
        },
    )

    assert response.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["accept", "revoke"])
async def test_other_client_cannot_modify_assignment(
    client, action
):
    assignment_id, _, _ = await setup_assignment(client)

    await register_client(client, "other-client")

    response = await client.post(
        f"{BASE}/{assignment_id}/{action}",
        headers=OTHER,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_other_doctor_cannot_access_case(client):
    assignment_id, _, _ = await setup_assignment(client)

    response = await client.post(
        f"{BASE}/{assignment_id}/accept",
        headers=CLIENT,
    )
    assert response.status_code == 200

    await register_doctor(client, "other-doctor")

    response = await client.get(
        f"{BASE}/doctor", headers=OTHER_DOCTOR
    )
    assert response.status_code == 200
    assert response.json() == []

    response = await client.post(
        f"{BASE}/{assignment_id}/complete",
        headers=OTHER_DOCTOR,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_doctor_can_complete_active_assignment(client):
    assignment_id, _, _ = await setup_assignment(client)

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
    assert response.json()["status"] == "completed"
    assert response.json()["ended_at"] is not None

    response = await client.get(
        f"{BASE}/doctor", headers=DOCTOR
    )
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_suspended_doctor_loses_access(client):
    assignment_id, _, application_id = await setup_assignment(client)

    response = await client.post(
        f"{BASE}/{assignment_id}/accept",
        headers=CLIENT,
    )
    assert response.status_code == 200

    response = await client.post(
        f"{ADMIN_BASE}/{application_id}/suspend",
        headers=ADMIN,
        json={"reason": "Synthetic suspension test."},
    )
    assert response.status_code == 200

    response = await client.get(
        f"{BASE}/doctor", headers=DOCTOR
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_assignment_does_not_share_ai_history(client):
    assignment_id, _, _ = await setup_assignment(client)

    response = await client.post(
        f"{BASE}/{assignment_id}/accept",
        headers=CLIENT,
    )
    assert response.status_code == 200

    response = await client.get(
        "/api/v1/conversations",
        headers=DOCTOR,
    )

    assert response.status_code == 403
