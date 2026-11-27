"""Verify takeover closure when professional assignments end."""

from uuid import UUID

import pytest

from app.config import settings
from app.models.human_takeover import HumanTakeover

from app.services.human_takeover_service import (
    request_takeover,
    accept_takeover,
    get_open_takeover,
)

from tests.conftest import TestAsyncSessionLocal

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

    return assignment_id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,auth_headers",
    [
        ("revoke", CLIENT),
        ("complete", DOCTOR),
    ],
)
@pytest.mark.parametrize(
    "activate,expected_status",
    [
        (False, "cancelled"),
        (True, "ended"),
    ],
)
async def test_assignment_closes_takeover(
    client,
    action,
    auth_headers,
    activate,
    expected_status,
):
    assignment_id = await setup_assignment(client)

    async with TestAsyncSessionLocal() as db:
        takeover = await request_takeover(
            db, UUID(assignment_id)
        )

        if activate:
            await accept_takeover(db, takeover)

        takeover_id = takeover.id

        await db.commit()

    response = await client.post(
        f"{ASSIGNMENTS}/{assignment_id}/{action}",
        headers=auth_headers,
    )

    assert response.status_code == 200

    async with TestAsyncSessionLocal() as db:
        takeover = await db.get(
            HumanTakeover, takeover_id
        )

        assert takeover.status == expected_status
        assert takeover.ended_at is not None

        if activate:
            assert takeover.accepted_at is not None
        else:
            assert takeover.accepted_at is None

        assert await get_open_takeover(
            db, UUID(assignment_id)
        ) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,auth_headers",
    [
        ("revoke", CLIENT),
        ("complete", DOCTOR),
    ],
)
async def test_assignment_without_takeover(
    client, action, auth_headers
):
    assignment_id = await setup_assignment(client)

    response = await client.post(
        f"{ASSIGNMENTS}/{assignment_id}/{action}",
        headers=auth_headers,
    )

    assert response.status_code == 200

    async with TestAsyncSessionLocal() as db:
        assert await get_open_takeover(
            db, UUID(assignment_id)
        ) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "action,auth_headers",
    [
        ("revoke", CLIENT),
        ("complete", DOCTOR),
    ],
)
@pytest.mark.parametrize("activate", [False, True])
async def test_takeover_closure_rollback(
    client,
    monkeypatch,
    action,
    auth_headers,
    activate,
):
    from app.api import assignments
    from app.models.doctor_assignment import DoctorAssignment
    from app.services.notification_service import create_notification
    from tests.test_notification_lifecycle import get_events

    assignment_id = await setup_assignment(client)

    async with TestAsyncSessionLocal() as db:
        assignment = await db.get(
            DoctorAssignment, UUID(assignment_id)
        )

        client_id = str(assignment.client_id)
        doctor_id = str(assignment.doctor_id)

        takeover = await request_takeover(
            db, UUID(assignment_id)
        )

        if activate:
            await accept_takeover(db, takeover)

        takeover_id = takeover.id

        await db.commit()

    client_events = await get_events(client_id)
    doctor_events = await get_events(doctor_id)

    async def failing_notification(db, **kwargs):
        await create_notification(db, **kwargs)

        raise RuntimeError(
            "Synthetic takeover notification failure"
        )

    monkeypatch.setattr(
        assignments,
        "create_notification",
        failing_notification,
    )

    with pytest.raises(
        RuntimeError,
        match="Synthetic takeover notification failure",
    ):
        await client.post(
            f"{ASSIGNMENTS}/{assignment_id}/{action}",
            headers=auth_headers,
        )

    async with TestAsyncSessionLocal() as db:
        assignment = await db.get(
            DoctorAssignment, UUID(assignment_id)
        )

        takeover = await db.get(
            HumanTakeover, takeover_id
        )

        assert assignment.status == "active"
        assert assignment.consented_at is not None
        assert assignment.ended_at is None

        expected_status = (
            "active" if activate else "requested"
        )

        assert takeover.status == expected_status
        assert takeover.ended_at is None

        if activate:
            assert takeover.accepted_at is not None
        else:
            assert takeover.accepted_at is None

        open_takeover = await get_open_takeover(
            db, UUID(assignment_id)
        )

        assert open_takeover.id == takeover_id

    assert await get_events(client_id) == client_events
    assert await get_events(doctor_id) == doctor_events
