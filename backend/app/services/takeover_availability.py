"""Resolve eligible human takeover sessions without exposing private data."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.user import User
from app.models.doctor_application import DoctorApplication
from app.models.doctor_assignment import DoctorAssignment
from app.models.human_takeover import HumanTakeover


async def get_eligible_active_takeover(
    db: AsyncSession,
    client_id: UUID,
) -> HumanTakeover | None:
    """Return an accepted takeover for an eligible client and doctor."""

    client = aliased(User)
    doctor = aliased(User)

    statement = (
        select(HumanTakeover)
        .join(
            DoctorAssignment,
            DoctorAssignment.id == HumanTakeover.assignment_id,
        )
        .join(
            client,
            client.id == DoctorAssignment.client_id,
        )
        .join(
            doctor,
            doctor.id == DoctorAssignment.doctor_id,
        )
        .join(
            DoctorApplication,
            DoctorApplication.user_id == doctor.id,
        )
        .where(
            DoctorAssignment.client_id == client_id,
            DoctorAssignment.status == "active",
            DoctorAssignment.consented_at.is_not(None),
            DoctorAssignment.ended_at.is_(None),

            client.role == "client",
            client.account_status == "active",

            doctor.role == "doctor",
            doctor.account_status == "active",
            doctor.is_verified.is_(True),

            DoctorApplication.status == "approved",
            DoctorApplication.reviewed_at.is_not(None),

            HumanTakeover.status == "active",
            HumanTakeover.consented_at.is_not(None),
            HumanTakeover.accepted_at.is_not(None),
            HumanTakeover.ended_at.is_(None),
        )
        .execution_options(populate_existing=True)
    )

    result = await db.execute(statement)

    return result.scalar_one_or_none()
