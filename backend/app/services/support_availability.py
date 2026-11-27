"""Check whether a client already has open support."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.support_request import SupportRequest
from app.models.doctor_assignment import DoctorAssignment


async def has_open_professional_support(
    db: AsyncSession,
    client_id: UUID,
) -> bool:

    result = await db.execute(
        select(SupportRequest.id)
        .where(
            SupportRequest.client_id == client_id,
            SupportRequest.status.in_(
                ["pending", "assigned"]
            ),
        )
        .limit(1)
    )

    if result.scalar_one_or_none() is not None:
        return True

    result = await db.execute(
        select(DoctorAssignment.id)
        .where(
            DoctorAssignment.client_id == client_id,
            DoctorAssignment.status.in_(
                ["pending", "active"]
            ),
        )
        .limit(1)
    )

    return result.scalar_one_or_none() is not None
