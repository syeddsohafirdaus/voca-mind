"""Tests for active human takeover eligibility."""

from uuid import UUID

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.user import User
from app.models.doctor_application import DoctorApplication

from app.services.human_takeover_service import (
    request_takeover,
    accept_takeover,
    cancel_takeover,
    end_takeover,
)

from app.services.takeover_availability import (
    get_eligible_active_takeover,
)

from tests.conftest import TestAsyncSessionLocal
from tests.test_assignments import register_client

from tests.test_notification_lifecycle import (
    setup_case,
    propose,
    accept,
    CLIENT,
    DOCTOR,
    ASSIGNMENTS,
)


@pytest.fixture(autouse=True)
def configure_admin(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "uid-assignment-admin",
    )


async def setup_assignment(client):
    client_id, doctor_id = await setup_case(client)

    assignment_id = await propose(
        client, client_id, doctor_id
    )

    await accept(client, assignment_id)

    return (
        UUID(client_id),
        UUID(doctor_id),
        UUID(assignment_id),
    )


@pytest.mark.asyncio
async def test_no_takeover(client):
    client_id, _, _ = await setup_assignment(client)

    async with TestAsyncSessionLocal() as db:
        assert await get_eligible_active_takeover(
            db, client_id
        ) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "takeover_status",
    ["requested", "active", "cancelled", "ended"],
)
async def test_takeover_status_eligibility(
    client, takeover_status
):
    client_id, _, assignment_id = (
        await setup_assignment(client)
    )

    async with TestAsyncSessionLocal() as db:
        takeover = await request_takeover(
            db, assignment_id
        )

        if takeover_status in ("active", "ended"):
            await accept_takeover(db, takeover)

        if takeover_status == "cancelled":
            await cancel_takeover(db, takeover)

        if takeover_status == "ended":
            await end_takeover(db, takeover)

        takeover_id = takeover.id

        await db.commit()

    async with TestAsyncSessionLocal() as db:
        result = await get_eligible_active_takeover(
            db, client_id
        )

        if takeover_status == "active":
            assert result is not None
            assert result.id == takeover_id
            assert result.assignment_id == assignment_id
        else:
            assert result is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "condition",
    [
        "doctor_suspended",
        "doctor_unverified",
        "doctor_application_rejected",
        "doctor_review_missing",
        "client_suspended",
    ],
)
async def test_ineligible_accounts(client, condition):
    client_id, doctor_id, assignment_id = (
        await setup_assignment(client)
    )

    async with TestAsyncSessionLocal() as db:
        takeover = await request_takeover(
            db, assignment_id
        )

        await accept_takeover(db, takeover)

        doctor = await db.get(User, doctor_id)
        client_user = await db.get(User, client_id)

        result = await db.execute(
            select(DoctorApplication).where(
                DoctorApplication.user_id == doctor_id
            )
        )

        application = result.scalar_one()

        if condition == "doctor_suspended":
            doctor.account_status = "suspended"

        elif condition == "doctor_unverified":
            doctor.is_verified = False

        elif condition == "doctor_application_rejected":
            application.status = "rejected"

        elif condition == "doctor_review_missing":
            application.reviewed_at = None

        elif condition == "client_suspended":
            client_user.account_status = "suspended"

        await db.commit()

    async with TestAsyncSessionLocal() as db:
        assert await get_eligible_active_takeover(
            db, client_id
        ) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,auth_headers",
    [
        ("revoke", CLIENT),
        ("complete", DOCTOR),
    ],
)
async def test_closed_assignment_ineligible(
    client, action, auth_headers
):
    client_id, _, assignment_id = (
        await setup_assignment(client)
    )

    async with TestAsyncSessionLocal() as db:
        takeover = await request_takeover(
            db, assignment_id
        )

        await accept_takeover(db, takeover)

        await db.commit()

    response = await client.post(
        f"{ASSIGNMENTS}/{assignment_id}/{action}",
        headers=auth_headers,
    )

    assert response.status_code == 200

    async with TestAsyncSessionLocal() as db:
        assert await get_eligible_active_takeover(
            db, client_id
        ) is None


@pytest.mark.asyncio
async def test_cross_client_isolation(client):
    client_id, _, assignment_id = (
        await setup_assignment(client)
    )

    other_client_id = UUID(
        await register_client(
            client, "other-takeover-client"
        )
    )

    async with TestAsyncSessionLocal() as db:
        takeover = await request_takeover(
            db, assignment_id
        )

        await accept_takeover(db, takeover)

        await db.commit()

    async with TestAsyncSessionLocal() as db:
        assert await get_eligible_active_takeover(
            db, client_id
        ) is not None

        assert await get_eligible_active_takeover(
            db, other_client_id
        ) is None
