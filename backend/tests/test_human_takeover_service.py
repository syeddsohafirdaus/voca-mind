"""Tests for human takeover lifecycle operations."""

from uuid import UUID

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.human_takeover import HumanTakeover

from app.services.human_takeover_service import (
    TakeoverConflict,
    get_open_takeover,
    request_takeover,
    accept_takeover,
    cancel_takeover,
    end_takeover,
    close_assignment_takeover,
)

from tests.conftest import TestAsyncSessionLocal

from tests.test_notification_lifecycle import (
    setup_case,
    propose,
    accept,
)


@pytest.fixture(autouse=True)
def configure_admin(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "uid-assignment-admin",
    )


async def setup_takeover_assignment(client):
    client_id, doctor_id = await setup_case(client)

    assignment_id = await propose(
        client, client_id, doctor_id
    )

    await accept(client, assignment_id)

    return UUID(assignment_id)


@pytest.mark.asyncio
async def test_no_open_takeover(client):
    assignment_id = await setup_takeover_assignment(client)

    async with TestAsyncSessionLocal() as db:
        assert await get_open_takeover(
            db, assignment_id
        ) is None


@pytest.mark.asyncio
async def test_request_takeover(client):
    assignment_id = await setup_takeover_assignment(client)

    async with TestAsyncSessionLocal() as db:
        takeover = await request_takeover(db, assignment_id)

        assert takeover.id is not None
        assert takeover.assignment_id == assignment_id
        assert takeover.status == "requested"
        assert takeover.consented_at is not None
        assert takeover.accepted_at is None
        assert takeover.ended_at is None

        await db.commit()


@pytest.mark.asyncio
async def test_find_open_takeover(client):
    assignment_id = await setup_takeover_assignment(client)

    async with TestAsyncSessionLocal() as db:
        takeover = await request_takeover(db, assignment_id)

        found = await get_open_takeover(db, assignment_id)

        assert found.id == takeover.id


@pytest.mark.asyncio
async def test_duplicate_pending_request(client):
    assignment_id = await setup_takeover_assignment(client)

    async with TestAsyncSessionLocal() as db:
        await request_takeover(db, assignment_id)

        with pytest.raises(TakeoverConflict):
            await request_takeover(db, assignment_id)


@pytest.mark.asyncio
async def test_accept_takeover(client):
    assignment_id = await setup_takeover_assignment(client)

    async with TestAsyncSessionLocal() as db:
        takeover = await request_takeover(db, assignment_id)

        await accept_takeover(db, takeover)

        assert takeover.status == "active"
        assert takeover.accepted_at is not None
        assert takeover.accepted_at >= takeover.consented_at
        assert takeover.ended_at is None


@pytest.mark.asyncio
async def test_duplicate_active_request(client):
    assignment_id = await setup_takeover_assignment(client)

    async with TestAsyncSessionLocal() as db:
        takeover = await request_takeover(db, assignment_id)

        await accept_takeover(db, takeover)

        with pytest.raises(TakeoverConflict):
            await request_takeover(db, assignment_id)


@pytest.mark.asyncio
async def test_duplicate_acceptance(client):
    assignment_id = await setup_takeover_assignment(client)

    async with TestAsyncSessionLocal() as db:
        takeover = await request_takeover(db, assignment_id)

        await accept_takeover(db, takeover)

        with pytest.raises(TakeoverConflict):
            await accept_takeover(db, takeover)


@pytest.mark.asyncio
async def test_cancel_pending_takeover(client):
    assignment_id = await setup_takeover_assignment(client)

    async with TestAsyncSessionLocal() as db:
        takeover = await request_takeover(db, assignment_id)

        await cancel_takeover(db, takeover)

        assert takeover.status == "cancelled"
        assert takeover.accepted_at is None
        assert takeover.ended_at is not None

        assert await get_open_takeover(
            db, assignment_id
        ) is None


@pytest.mark.asyncio
async def test_cannot_accept_cancelled_takeover(client):
    assignment_id = await setup_takeover_assignment(client)

    async with TestAsyncSessionLocal() as db:
        takeover = await request_takeover(db, assignment_id)

        await cancel_takeover(db, takeover)

        with pytest.raises(TakeoverConflict):
            await accept_takeover(db, takeover)


@pytest.mark.asyncio
async def test_cannot_cancel_active_takeover(client):
    assignment_id = await setup_takeover_assignment(client)

    async with TestAsyncSessionLocal() as db:
        takeover = await request_takeover(db, assignment_id)

        await accept_takeover(db, takeover)

        with pytest.raises(TakeoverConflict):
            await cancel_takeover(db, takeover)


@pytest.mark.asyncio
async def test_cannot_end_pending_takeover(client):
    assignment_id = await setup_takeover_assignment(client)

    async with TestAsyncSessionLocal() as db:
        takeover = await request_takeover(db, assignment_id)

        with pytest.raises(TakeoverConflict):
            await end_takeover(db, takeover)


@pytest.mark.asyncio
async def test_end_active_takeover(client):
    assignment_id = await setup_takeover_assignment(client)

    async with TestAsyncSessionLocal() as db:
        takeover = await request_takeover(db, assignment_id)

        await accept_takeover(db, takeover)
        await end_takeover(db, takeover)

        assert takeover.status == "ended"
        assert takeover.ended_at is not None
        assert takeover.ended_at >= takeover.accepted_at

        assert await get_open_takeover(
            db, assignment_id
        ) is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "activate,expected_status",
    [
        (False, "cancelled"),
        (True, "ended"),
    ],
)
async def test_assignment_closure(
    client, activate, expected_status
):
    assignment_id = await setup_takeover_assignment(client)

    async with TestAsyncSessionLocal() as db:
        takeover = await request_takeover(db, assignment_id)

        if activate:
            await accept_takeover(db, takeover)

        closed = await close_assignment_takeover(
            db, assignment_id
        )

        assert closed.id == takeover.id
        assert closed.status == expected_status
        assert closed.ended_at is not None

        assert await close_assignment_takeover(
            db, assignment_id
        ) is None


@pytest.mark.asyncio
async def test_new_request_after_session_ends(client):
    assignment_id = await setup_takeover_assignment(client)

    async with TestAsyncSessionLocal() as db:
        first = await request_takeover(db, assignment_id)

        await accept_takeover(db, first)
        await end_takeover(db, first)

        second = await request_takeover(db, assignment_id)

        assert first.id != second.id
        assert first.status == "ended"
        assert second.status == "requested"

        await db.commit()

    async with TestAsyncSessionLocal() as db:
        result = await db.execute(
            select(HumanTakeover).where(
                HumanTakeover.assignment_id == assignment_id
            )
        )

        sessions = result.scalars().all()

        assert len(sessions) == 2
        assert {s.status for s in sessions} == {
            "ended", "requested"
        }
