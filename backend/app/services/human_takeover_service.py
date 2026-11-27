"""Lifecycle operations for consent-based human takeover."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.human_takeover import HumanTakeover


OPEN_STATUSES = ("requested", "active")


class TakeoverConflict(Exception):
    """Invalid human takeover state transition."""


async def get_open_takeover(
    db: AsyncSession,
    assignment_id: UUID,
) -> HumanTakeover | None:
    result = await db.execute(
        select(HumanTakeover)
        .where(
            HumanTakeover.assignment_id == assignment_id,
            HumanTakeover.status.in_(OPEN_STATUSES),
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    return result.scalar_one_or_none()


async def request_takeover(
    db: AsyncSession,
    assignment_id: UUID,
) -> HumanTakeover:
    existing = await get_open_takeover(
        db, assignment_id
    )

    if existing is not None:
        raise TakeoverConflict(
            "An open takeover session already exists"
        )

    now = datetime.now(timezone.utc)

    takeover = HumanTakeover(
        assignment_id=assignment_id,
        status="requested",
        consented_at=now,
        created_at=now,
    )

    db.add(takeover)
    await db.flush()

    return takeover


async def accept_takeover(
    db: AsyncSession,
    takeover: HumanTakeover,
) -> HumanTakeover:
    if takeover.status != "requested":
        raise TakeoverConflict(
            "Takeover request is not pending"
        )

    takeover.status = "active"
    takeover.accepted_at = datetime.now(timezone.utc)

    await db.flush()

    return takeover


async def cancel_takeover(
    db: AsyncSession,
    takeover: HumanTakeover,
) -> HumanTakeover:
    if takeover.status != "requested":
        raise TakeoverConflict(
            "Only pending takeover requests can be cancelled"
        )

    takeover.status = "cancelled"
    takeover.ended_at = datetime.now(timezone.utc)

    await db.flush()

    return takeover


async def end_takeover(
    db: AsyncSession,
    takeover: HumanTakeover,
) -> HumanTakeover:
    if takeover.status != "active":
        raise TakeoverConflict(
            "Takeover session is not active"
        )

    takeover.status = "ended"
    takeover.ended_at = datetime.now(timezone.utc)

    await db.flush()

    return takeover


async def close_assignment_takeover(
    db: AsyncSession,
    assignment_id: UUID,
) -> HumanTakeover | None:
    takeover = await get_open_takeover(
        db, assignment_id
    )

    if takeover is None:
        return None

    if takeover.status == "requested":
        return await cancel_takeover(db, takeover)

    return await end_takeover(db, takeover)
