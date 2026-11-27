"""Privacy and transaction tests for takeover notifications."""

import pytest

from sqlalchemy import select
from uuid import UUID

from app.config import settings
from app.models.notification import Notification
from app.models.human_takeover import HumanTakeover

from tests.conftest import TestAsyncSessionLocal
from tests.test_assignments import (
    CLIENT,
    DOCTOR,
    get_user_id,
)
from tests.test_takeover_endpoints import (
    BASE,
    prepare_assignment,
    request_session,
    accept_session,
)


@pytest.fixture(autouse=True)
def configure_admin(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "uid-assignment-admin",
    )


async def get_takeover_events(user_id):
    async with TestAsyncSessionLocal() as db:
        result = await db.execute(
            select(Notification)
            .where(
                Notification.recipient_id == UUID(user_id),
                Notification.event_type.like("takeover_%"),
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


@pytest.mark.asyncio
async def test_takeover_notification_lifecycle(client):
    assignment_id, _ = await prepare_assignment(client)

    client_id = await get_user_id("assignment-client")
    doctor_id = await get_user_id("assignment-doctor")

    requested = await request_session(
        client, assignment_id
    )

    session_id = requested["id"]

    assert await get_takeover_events(doctor_id) == [
        ("takeover_requested", session_id)
    ]

    assert await get_takeover_events(client_id) == []

    await accept_session(client, assignment_id, requested["id"])

    assert await get_takeover_events(client_id) == [
        ("takeover_accepted", session_id)
    ]

    response = await client.post(
        f"{BASE}/{assignment_id}/end?takeover_id={requested['id']}",
        headers=CLIENT,
    )

    assert response.status_code == 200

    assert await get_takeover_events(doctor_id) == [
        ("takeover_requested", session_id),
        ("takeover_ended", session_id),
    ]


@pytest.mark.asyncio
async def test_cancel_notification(client):
    assignment_id, _ = await prepare_assignment(client)

    doctor_id = await get_user_id("assignment-doctor")

    requested = await request_session(
        client, assignment_id
    )

    response = await client.post(
        f"{BASE}/{assignment_id}/cancel?takeover_id={requested['id']}",
        headers=CLIENT,
    )

    assert response.status_code == 200

    assert await get_takeover_events(doctor_id) == [
        ("takeover_requested", requested["id"]),
        ("takeover_cancelled", requested["id"]),
    ]


@pytest.mark.asyncio
async def test_doctor_end_notifies_client(client):
    assignment_id, _ = await prepare_assignment(client)

    client_id = await get_user_id("assignment-client")

    requested = await request_session(
        client, assignment_id
    )

    await accept_session(client, assignment_id, requested["id"])

    response = await client.post(
        f"{BASE}/{assignment_id}/end?takeover_id={requested['id']}",
        headers=DOCTOR,
    )

    assert response.status_code == 200

    assert await get_takeover_events(client_id) == [
        ("takeover_accepted", requested["id"]),
        ("takeover_ended", requested["id"]),
    ]


@pytest.mark.asyncio
async def test_duplicate_request_does_not_notify_twice(client):
    assignment_id, _ = await prepare_assignment(client)

    doctor_id = await get_user_id("assignment-doctor")

    requested = await request_session(
        client, assignment_id
    )

    response = await client.post(
        f"{BASE}/{assignment_id}/request",
        headers=CLIENT,
        json={"consent": True},
    )

    assert response.status_code == 409

    assert await get_takeover_events(doctor_id) == [
        ("takeover_requested", requested["id"])
    ]


@pytest.mark.asyncio
async def test_takeover_notification_privacy(client):
    assignment_id, _ = await prepare_assignment(client)

    requested = await request_session(
        client, assignment_id
    )

    response = await client.get(
        "/api/v1/notifications",
        headers=DOCTOR,
    )

    assert response.status_code == 200

    event = next(
        item for item in response.json()
        if item["event_type"] == "takeover_requested"
    )

    assert set(event) == {
        "id",
        "event_type",
        "reference_id",
        "created_at",
        "read_at",
    }

    assert event["reference_id"] == requested["id"]

    response = await client.get(
        "/api/v1/notifications",
        headers=CLIENT,
    )

    assert response.status_code == 200

    assert all(
        item["id"] != event["id"]
        for item in response.json()
    )


@pytest.mark.asyncio
async def test_takeover_notification_cannot_be_read_by_other(client):
    assignment_id, _ = await prepare_assignment(client)

    await request_session(client, assignment_id)

    response = await client.get(
        "/api/v1/notifications",
        headers=DOCTOR,
    )

    event = next(
        item for item in response.json()
        if item["event_type"] == "takeover_requested"
    )

    response = await client.post(
        f"/api/v1/notifications/{event['id']}/read",
        headers=CLIENT,
    )

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,initial_status,auth",
    [
        ("request", None, CLIENT),
        ("accept", "requested", DOCTOR),
        ("cancel", "requested", CLIENT),
        ("end", "active", CLIENT),
    ],
)
async def test_notification_failure_rolls_back_takeover(
    client,
    monkeypatch,
    action,
    initial_status,
    auth,
):
    from app.api import takeovers

    assignment_id, _ = await prepare_assignment(client)

    client_id = await get_user_id("assignment-client")
    doctor_id = await get_user_id("assignment-doctor")

    if initial_status is not None:
        requested = await request_session(client, assignment_id)

    if initial_status == "active":
        await accept_session(client, assignment_id, requested["id"])

    before_client = await get_takeover_events(client_id)
    before_doctor = await get_takeover_events(doctor_id)

    original = takeovers.create_notification

    async def failing_notification(*args, **kwargs):
        await original(*args, **kwargs)
        raise RuntimeError(
            "Synthetic notification failure"
        )

    monkeypatch.setattr(
        takeovers,
        "create_notification",
        failing_notification,
    )

    kwargs = {"headers": auth}

    if action == "request":
        kwargs["json"] = {"consent": True}
    else:
        kwargs["params"] = {"takeover_id": requested["id"]}

    try:
        response = await client.post(
            f"{BASE}/{assignment_id}/{action}",
            **kwargs,
        )
    except RuntimeError as exc:
        assert str(exc) == (
            "Synthetic notification failure"
        )
    else:
        assert response.status_code == 500

    async with TestAsyncSessionLocal() as db:
        result = await db.execute(
            select(HumanTakeover).where(
                HumanTakeover.assignment_id
                == UUID(assignment_id)
            )
        )

        takeover = result.scalar_one_or_none()

        if initial_status is None:
            assert takeover is None
        else:
            assert takeover is not None
            assert takeover.status == initial_status

    assert await get_takeover_events(client_id) == before_client
    assert await get_takeover_events(doctor_id) == before_doctor
