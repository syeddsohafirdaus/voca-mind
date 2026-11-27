"""Professional authorization and privacy tests."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app.database import get_db
from app.main import app
from app.models.user import User
from app.models.doctor_application import DoctorApplication


DASHBOARD = "/api/v1/doctors/dashboard"


def headers(token):
    return {"Authorization": f"Bearer {token}"}


async def register_doctor(client):
    response = await client.post(
        "/api/v1/auth/register/doctor",
        headers=headers("doctor-test"),
        json={
            "display_name": "Synthetic Test Doctor",
            "registration_number": "TEST-12345",
            "licensing_authority": "Test Authority",
            "specialization": "Psychiatry",
        },
    )
    assert response.status_code == 201


async def configure_doctor(
    account_status,
    verified,
    application_status,
    reviewed,
):
    # Uses the isolated test database only.
    async for db in app.dependency_overrides[get_db]():
        result = await db.execute(
            select(User).where(
                User.firebase_uid == "uid-doctor-test"
            )
        )
        doctor = result.scalar_one()

        doctor.account_status = account_status
        doctor.is_verified = verified

        result = await db.execute(
            select(DoctorApplication).where(
                DoctorApplication.user_id == doctor.id
            )
        )
        application = result.scalar_one()

        if application_status is None:
            await db.delete(application)
        else:
            application.status = application_status
            application.reviewed_at = (
                datetime.now(timezone.utc)
                if reviewed else None
            )

        await db.commit()


@pytest.mark.asyncio
async def test_unauthenticated_doctor_dashboard(client):
    response = await client.get(DASHBOARD)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token(client):
    response = await client.get(
        DASHBOARD,
        headers=headers("invalid-token"),
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_unregistered_account(client):
    response = await client.get(
        DASHBOARD,
        headers=headers("unregistered-test"),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["client", "guardian"])
async def test_non_doctor_roles_denied(client, role):
    payload = {"display_name": "Synthetic Test User"}

    if role == "client":
        payload["date_of_birth"] = "2003-01-15"

    response = await client.post(
        f"/api/v1/auth/register/{role}",
        headers=headers("non-doctor-test"),
        json=payload,
    )
    assert response.status_code == 201

    response = await client.get(
        DASHBOARD,
        headers=headers("non-doctor-test"),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "account_status,verified,application_status,reviewed",
    [
        ("pending", False, "pending", False),
        ("pending", True, "approved", True),
        ("suspended", True, "approved", True),
        ("active", False, "approved", True),
        ("active", True, None, False),
        ("active", True, "pending", False),
        ("active", True, "rejected", True),
        ("active", True, "approved", False),
    ],
)
async def test_ineligible_doctors_denied(
    client,
    account_status,
    verified,
    application_status,
    reviewed,
):
    await register_doctor(client)

    await configure_doctor(
        account_status,
        verified,
        application_status,
        reviewed,
    )

    response = await client.get(
        DASHBOARD,
        headers=headers("doctor-test"),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_approved_doctor_access_and_privacy(client):
    await register_doctor(client)

    await configure_doctor(
        "active",
        True,
        "approved",
        True,
    )

    response = await client.get(
        DASHBOARD,
        headers=headers("doctor-test"),
    )

    assert response.status_code == 200

    assert response.json() == {
        "display_name": "Synthetic Test Doctor",
        "role": "doctor",
        "account_status": "active",
        "is_verified": True,
        "dashboard_access": True,
    }

    # Verified professionals must not automatically
    # gain access to private AI conversations.
    response = await client.get(
        "/api/v1/conversations",
        headers=headers("doctor-test"),
    )

    assert response.status_code == 403
