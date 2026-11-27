"""Notification transaction atomicity tests."""

from uuid import UUID

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.support_request import SupportRequest
from app.models.doctor_assignment import DoctorAssignment
from app.models.professional_message import ProfessionalMessage

from app.api import support_requests
from app.api import assignments
from app.api import professional_messages

from app.services.notification_service import create_notification

from tests.conftest import TestAsyncSessionLocal

from tests.test_notification_lifecycle import (
    setup_case,
    propose,
    accept,
    get_events,
    CLIENT,
    DOCTOR,
    ADMIN,
    SUPPORT,
    ASSIGNMENTS,
    PROFESSIONAL,
)


@pytest.fixture(autouse=True)
def configure_admin(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "uid-assignment-admin",
    )


async def failing_notification(db, **kwargs):
    await create_notification(db, **kwargs)

    raise RuntimeError(
        "Synthetic notification failure"
    )


@pytest.mark.asyncio
async def test_support_request_rollback(client, monkeypatch):
    client_id, doctor_id = await setup_case(client)

    monkeypatch.setattr(
        support_requests,
        "create_notification",
        failing_notification,
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic notification failure",
    ):
        await client.post(
            f"{SUPPORT}/request",
            headers=CLIENT,
            json={
                "source": "client",
                "consent": True,
            },
        )

    async with TestAsyncSessionLocal() as db:
        result = await db.execute(
            select(SupportRequest).where(
                SupportRequest.client_id == UUID(client_id)
            )
        )

        assert result.scalars().all() == []

    assert await get_events(client_id) == []
    assert await get_events(doctor_id) == []


@pytest.mark.asyncio
async def test_assignment_proposal_rollback(client, monkeypatch):
    client_id, doctor_id = await setup_case(client)

    monkeypatch.setattr(
        assignments,
        "create_notification",
        failing_notification,
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic notification failure",
    ):
        await client.post(
            f"{ASSIGNMENTS}/propose",
            headers=ADMIN,
            json={
                "client_id": client_id,
                "doctor_id": doctor_id,
            },
        )

    async with TestAsyncSessionLocal() as db:
        result = await db.execute(
            select(DoctorAssignment).where(
                DoctorAssignment.client_id == UUID(client_id)
            )
        )

        assert result.scalars().all() == []

    assert await get_events(client_id) == []
    assert await get_events(doctor_id) == []


@pytest.mark.asyncio
async def test_assignment_acceptance_rollback(client, monkeypatch):
    client_id, doctor_id = await setup_case(client)

    assignment_id = await propose(
        client, client_id, doctor_id
    )

    monkeypatch.setattr(
        assignments,
        "create_notification",
        failing_notification,
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic notification failure",
    ):
        await client.post(
            f"{ASSIGNMENTS}/{assignment_id}/accept",
            headers=CLIENT,
        )

    async with TestAsyncSessionLocal() as db:
        assignment = await db.get(
            DoctorAssignment,
            UUID(assignment_id),
        )

        assert assignment.status == "pending"
        assert assignment.consented_at is None

    assert await get_events(doctor_id) == []

    assert await get_events(client_id) == [
        ("assignment_proposed", assignment_id)
    ]


@pytest.mark.asyncio
async def test_professional_message_rollback(client, monkeypatch):
    client_id, doctor_id = await setup_case(client)

    assignment_id = await propose(
        client, client_id, doctor_id
    )

    await accept(client, assignment_id)

    monkeypatch.setattr(
        professional_messages,
        "create_notification",
        failing_notification,
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic notification failure",
    ):
        await client.post(
            f"{PROFESSIONAL}/{assignment_id}/messages",
            headers=CLIENT,
            json={
                "content": "Synthetic rollback test message"
            },
        )

    async with TestAsyncSessionLocal() as db:
        result = await db.execute(
            select(ProfessionalMessage).where(
                ProfessionalMessage.assignment_id
                == UUID(assignment_id)
            )
        )

        assert result.scalars().all() == []

    assert await get_events(doctor_id) == [
        ("assignment_accepted", assignment_id)
    ]

    assert await get_events(client_id) == [
        ("assignment_proposed", assignment_id)
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,auth_headers",
    [
        ("revoke", CLIENT),
        ("complete", DOCTOR),
    ],
)
async def test_assignment_closure_rollback(
    client, monkeypatch, action, auth_headers
):
    client_id, doctor_id = await setup_case(client)

    response = await client.post(
        f"{SUPPORT}/request",
        headers=CLIENT,
        json={
            "source": "client",
            "consent": True,
        },
    )

    assert response.status_code == 201

    request_id = response.json()["id"]

    assignment_id = await propose(
        client, client_id, doctor_id
    )

    await accept(client, assignment_id)

    client_events = await get_events(client_id)
    doctor_events = await get_events(doctor_id)

    monkeypatch.setattr(
        assignments,
        "create_notification",
        failing_notification,
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic notification failure",
    ):
        await client.post(
            f"{ASSIGNMENTS}/{assignment_id}/{action}",
            headers=auth_headers,
        )

    async with TestAsyncSessionLocal() as db:
        assignment = await db.get(
            DoctorAssignment,
            UUID(assignment_id),
        )

        request = await db.get(
            SupportRequest,
            UUID(request_id),
        )

        assert assignment.status == "active"
        assert assignment.consented_at is not None
        assert assignment.ended_at is None

        assert request.status == "assigned"
        assert request.ended_at is None
        assert request.assignment_id == UUID(assignment_id)

    assert await get_events(client_id) == client_events
    assert await get_events(doctor_id) == doctor_events


@pytest.mark.asyncio
async def test_linked_proposal_rollback(client, monkeypatch):
    client_id, doctor_id = await setup_case(client)

    response = await client.post(
        f"{SUPPORT}/request",
        headers=CLIENT,
        json={"source": "client", "consent": True},
    )

    assert response.status_code == 201

    request_id = response.json()["id"]

    monkeypatch.setattr(
        assignments,
        "create_notification",
        failing_notification,
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic notification failure",
    ):
        await client.post(
            f"{ASSIGNMENTS}/propose",
            headers=ADMIN,
            json={
                "client_id": client_id,
                "doctor_id": doctor_id,
                "support_request_id": request_id,
            },
        )

    async with TestAsyncSessionLocal() as db:
        request = await db.get(
            SupportRequest,
            UUID(request_id),
        )

        assert request.status == "pending"
        assert request.assignment_id is None
        assert request.ended_at is None

        result = await db.execute(
            select(DoctorAssignment).where(
                DoctorAssignment.client_id == UUID(client_id)
            )
        )

        assert result.scalars().all() == []

    assert await get_events(client_id) == [
        ("support_requested", request_id)
    ]

    assert await get_events(doctor_id) == []
