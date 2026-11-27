"""Professional verification lifecycle integration tests."""

import uuid

import pytest
from sqlalchemy import select

from app.config import settings
from app.database import get_db
from app.main import app
from app.models.doctor_review import DoctorReview


BASE = "/api/v1/admin/doctor-applications"
DASHBOARD = "/api/v1/doctors/dashboard"

ADMIN = {"Authorization": "Bearer admin-test"}
DOCTOR = {"Authorization": "Bearer doctor-review-test"}

REASON = {"reason": "Synthetic credential review for testing."}


@pytest.fixture(autouse=True)
def configure_admin(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "uid-admin-test",
    )


async def create_application(client):
    response = await client.post(
        "/api/v1/auth/register/doctor",
        headers=DOCTOR,
        json={
            "display_name": "Synthetic Professional",
            "registration_number": "TEST-12345",
            "licensing_authority": "Test Authority",
            "specialization": "Psychiatry",
        },
    )
    assert response.status_code == 201

    response = await client.get(BASE, headers=ADMIN)
    assert response.status_code == 200

    applications = response.json()
    assert len(applications) == 1

    return applications[0]["id"]


@pytest.mark.asyncio
async def test_unauthenticated_admin(client):
    response = await client.get(BASE)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_admin_token(client):
    response = await client.get(
        BASE,
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_ordinary_user_denied(client):
    response = await client.get(BASE, headers=DOCTOR)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_application_listing_and_details(client):
    application_id = await create_application(client)

    response = await client.get(
        f"{BASE}/{application_id}",
        headers=ADMIN,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert response.json()["is_verified"] is False

    response = await client.get(
        f"{BASE}?status=approved",
        headers=ADMIN,
    )

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_approval_unlocks_dashboard(client):
    application_id = await create_application(client)

    response = await client.get(
        DASHBOARD, headers=DOCTOR
    )
    assert response.status_code == 403

    response = await client.post(
        f"{BASE}/{application_id}/approve",
        headers=ADMIN,
        json=REASON,
    )

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "approved"
    assert data["account_status"] == "active"
    assert data["is_verified"] is True
    assert data["reviewed_at"] is not None

    response = await client.get(
        DASHBOARD, headers=DOCTOR
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_rejection_blocks_access(client):
    application_id = await create_application(client)

    response = await client.post(
        f"{BASE}/{application_id}/reject",
        headers=ADMIN,
        json=REASON,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["account_status"] == "suspended"
    assert response.json()["is_verified"] is False

    response = await client.get(
        DASHBOARD, headers=DOCTOR
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_suspension_revokes_access(client):
    application_id = await create_application(client)

    response = await client.post(
        f"{BASE}/{application_id}/approve",
        headers=ADMIN,
        json=REASON,
    )
    assert response.status_code == 200

    response = await client.post(
        f"{BASE}/{application_id}/suspend",
        headers=ADMIN,
        json=REASON,
    )

    assert response.status_code == 200
    assert response.json()["account_status"] == "suspended"
    assert response.json()["is_verified"] is False

    response = await client.get(
        DASHBOARD, headers=DOCTOR
    )
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action", ["approve", "reject", "suspend"]
)
async def test_unauthorized_review(client, action):
    application_id = await create_application(client)

    response = await client.post(
        f"{BASE}/{application_id}/{action}",
        headers=DOCTOR,
        json=REASON,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_cannot_self_approve(
    client, monkeypatch
):
    application_id = await create_application(client)

    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "uid-doctor-review-test",
    )

    response = await client.post(
        f"{BASE}/{application_id}/approve",
        headers=DOCTOR,
        json=REASON,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_approval_rejected(client):
    application_id = await create_application(client)

    url = f"{BASE}/{application_id}/approve"

    first = await client.post(
        url, headers=ADMIN, json=REASON
    )
    second = await client.post(
        url, headers=ADMIN, json=REASON
    )

    assert first.status_code == 200
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_missing_application(client):
    response = await client.post(
        f"{BASE}/{uuid.uuid4()}/approve",
        headers=ADMIN,
        json=REASON,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_review_reason_required(client):
    application_id = await create_application(client)

    response = await client.post(
        f"{BASE}/{application_id}/approve",
        headers=ADMIN,
        json={"reason": " "},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_pending_doctor_cannot_be_suspended(client):
    application_id = await create_application(client)

    response = await client.post(
        f"{BASE}/{application_id}/suspend",
        headers=ADMIN,
        json=REASON,
    )

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_audit_history(client):
    application_id = await create_application(client)

    for action in ["approve", "suspend"]:
        response = await client.post(
            f"{BASE}/{application_id}/{action}",
            headers=ADMIN,
            json=REASON,
        )
        assert response.status_code == 200

    async for db in app.dependency_overrides[get_db]():
        result = await db.execute(
            select(DoctorReview).where(
                DoctorReview.application_id
                == uuid.UUID(application_id)
            ).order_by(DoctorReview.created_at)
        )

        reviews = result.scalars().all()

        assert len(reviews) == 2

        assert reviews[0].decision == "approved"
        assert reviews[0].previous_status == "pending"

        assert reviews[1].decision == "suspended"
        assert reviews[1].previous_status == "approved"

        for review in reviews:
            assert review.reviewer_uid == "uid-admin-test"
            assert review.reason == REASON["reason"]
            assert review.created_at is not None
