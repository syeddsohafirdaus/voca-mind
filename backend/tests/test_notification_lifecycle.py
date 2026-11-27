"""Notification lifecycle integration tests."""

from uuid import UUID

import pytest

from sqlalchemy import select

from app.config import settings
from app.models.notification import Notification
from app.models.professional_message import ProfessionalMessage

from tests.conftest import TestAsyncSessionLocal

from tests.test_assignments import (
    register_client,
    register_doctor,
    headers,
)

SUPPORT = "/api/v1/support"
ASSIGNMENTS = "/api/v1/assignments"
PROFESSIONAL = "/api/v1/professional"

ADMIN = headers("assignment-admin")
CLIENT = headers("notify-client")
DOCTOR = headers("notify-doctor")


@pytest.fixture(autouse=True)
def configure_admin(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "uid-assignment-admin",
    )


async def get_events(recipient_id):
    async with TestAsyncSessionLocal() as db:
        result = await db.execute(
            select(Notification)
            .where(
                Notification.recipient_id == UUID(recipient_id)
            )
            .order_by(
                Notification.created_at,
                Notification.id,
            )
        )

        return [
            (item.event_type, str(item.reference_id))
            for item in result.scalars().all()
        ]


async def setup_case(client):
    client_id = await register_client(
        client, "notify-client"
    )

    doctor_id, _ = await register_doctor(
        client, "notify-doctor"
    )

    return client_id, doctor_id


async def propose(client, client_id, doctor_id):
    response = await client.post(
        f"{ASSIGNMENTS}/propose",
        headers=ADMIN,
        json={
            "client_id": client_id,
            "doctor_id": doctor_id,
        },
    )

    assert response.status_code == 201

    return response.json()["id"]


async def accept(client, assignment_id):
    response = await client.post(
        f"{ASSIGNMENTS}/{assignment_id}/accept",
        headers=CLIENT,
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_support_request_notification(client):
    client_id, doctor_id = await setup_case(client)

    response = await client.post(
        f"{SUPPORT}/request",
        headers=CLIENT,
        json={"source": "client", "consent": True},
    )

    assert response.status_code == 201

    request_id = response.json()["id"]

    assert await get_events(client_id) == [
        ("support_requested", request_id)
    ]

    assert await get_events(doctor_id) == []


@pytest.mark.asyncio
async def test_proposal_notification_client_only(client):
    client_id, doctor_id = await setup_case(client)

    assignment_id = await propose(
        client, client_id, doctor_id
    )

    assert await get_events(client_id) == [
        ("assignment_proposed", assignment_id)
    ]

    assert await get_events(doctor_id) == []


@pytest.mark.asyncio
async def test_acceptance_notification_doctor_only(client):
    client_id, doctor_id = await setup_case(client)

    assignment_id = await propose(
        client, client_id, doctor_id
    )

    await accept(client, assignment_id)

    assert await get_events(doctor_id) == [
        ("assignment_accepted", assignment_id)
    ]

    assert await get_events(client_id) == [
        ("assignment_proposed", assignment_id)
    ]


@pytest.mark.asyncio
async def test_active_revocation_notification(client):
    client_id, doctor_id = await setup_case(client)

    assignment_id = await propose(
        client, client_id, doctor_id
    )

    await accept(client, assignment_id)

    response = await client.post(
        f"{ASSIGNMENTS}/{assignment_id}/revoke",
        headers=CLIENT,
    )

    assert response.status_code == 200

    assert await get_events(doctor_id) == [
        ("assignment_accepted", assignment_id),
        ("assignment_revoked", assignment_id),
    ]


@pytest.mark.asyncio
async def test_declining_does_not_notify_doctor(client):
    client_id, doctor_id = await setup_case(client)

    assignment_id = await propose(
        client, client_id, doctor_id
    )

    response = await client.post(
        f"{ASSIGNMENTS}/{assignment_id}/revoke",
        headers=CLIENT,
    )

    assert response.status_code == 200
    assert await get_events(doctor_id) == []


@pytest.mark.asyncio
async def test_completion_notification(client):
    client_id, doctor_id = await setup_case(client)

    assignment_id = await propose(
        client, client_id, doctor_id
    )

    await accept(client, assignment_id)

    response = await client.post(
        f"{ASSIGNMENTS}/{assignment_id}/complete",
        headers=DOCTOR,
    )

    assert response.status_code == 200

    assert await get_events(client_id) == [
        ("assignment_proposed", assignment_id),
        ("assignment_completed", assignment_id),
    ]

    assert await get_events(doctor_id) == [
        ("assignment_accepted", assignment_id)
    ]


@pytest.mark.asyncio
async def test_two_way_message_notifications(client):
    client_id, doctor_id = await setup_case(client)

    assignment_id = await propose(
        client, client_id, doctor_id
    )

    await accept(client, assignment_id)

    url = f"{PROFESSIONAL}/{assignment_id}/messages"

    response = await client.post(
        url,
        headers=CLIENT,
        json={"content": "Synthetic private client message"},
    )

    assert response.status_code == 201

    assert await get_events(doctor_id) == [
        ("assignment_accepted", assignment_id),
        ("professional_message", assignment_id),
    ]

    response = await client.post(
        url,
        headers=DOCTOR,
        json={"content": "Synthetic professional reply"},
    )

    assert response.status_code == 201

    assert await get_events(client_id) == [
        ("assignment_proposed", assignment_id),
        ("professional_message", assignment_id),
    ]


@pytest.mark.asyncio
async def test_pending_message_creates_no_notification(client):
    client_id, doctor_id = await setup_case(client)

    assignment_id = await propose(
        client, client_id, doctor_id
    )

    response = await client.post(
        f"{PROFESSIONAL}/{assignment_id}/messages",
        headers=CLIENT,
        json={"content": "Blocked synthetic message"},
    )

    assert response.status_code == 403
    assert await get_events(doctor_id) == []

    assert await get_events(client_id) == [
        ("assignment_proposed", assignment_id)
    ]


@pytest.mark.asyncio
async def test_duplicate_acceptance_no_notification(client):
    client_id, doctor_id = await setup_case(client)

    assignment_id = await propose(
        client, client_id, doctor_id
    )

    await accept(client, assignment_id)

    response = await client.post(
        f"{ASSIGNMENTS}/{assignment_id}/accept",
        headers=CLIENT,
    )

    assert response.status_code == 409

    assert await get_events(doctor_id) == [
        ("assignment_accepted", assignment_id)
    ]


@pytest.mark.asyncio
async def test_unauthorized_message_no_notification(client):
    client_id, doctor_id = await setup_case(client)

    other_id = await register_client(
        client, "notify-other"
    )

    assignment_id = await propose(
        client, client_id, doctor_id
    )

    await accept(client, assignment_id)

    response = await client.post(
        f"{PROFESSIONAL}/{assignment_id}/messages",
        headers=headers("notify-other"),
        json={"content": "Unauthorized synthetic message"},
    )

    assert response.status_code == 404

    assert await get_events(other_id) == []

    assert await get_events(doctor_id) == [
        ("assignment_accepted", assignment_id)
    ]

    assert await get_events(client_id) == [
        ("assignment_proposed", assignment_id)
    ]
