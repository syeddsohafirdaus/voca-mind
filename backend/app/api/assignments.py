"""Consent-based professional assignment endpoints."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.admin import require_platform_admin
from app.auth.dependencies import (
    require_role,
    require_verified_doctor,
)
from app.database import get_db
from app.models.user import User
from app.models.doctor_application import DoctorApplication
from app.models.doctor_assignment import DoctorAssignment
from app.models.support_request import SupportRequest


router = APIRouter()


class AssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: UUID
    doctor_id: UUID


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    doctor_id: UUID
    status: str
    consented_at: datetime | None
    ended_at: datetime | None
    created_at: datetime


async def eligible_doctor(db, doctor_id):
    result = await db.execute(
        select(User)
        .join(
            DoctorApplication,
            DoctorApplication.user_id == User.id,
        )
        .where(
            User.id == doctor_id,
            User.role == "doctor",
            User.account_status == "active",
            User.is_verified.is_(True),
            DoctorApplication.status == "approved",
            DoctorApplication.reviewed_at.is_not(None),
        )
        .with_for_update()
    )

    return result.scalar_one_or_none()


@router.post(
    "/propose",
    response_model=AssignmentResponse,
    status_code=201,
)
async def propose_assignment(
    payload: AssignmentRequest,
    admin_uid: str = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    if payload.client_id == payload.doctor_id:
        raise HTTPException(400, "Invalid assignment")

    result = await db.execute(
        select(User).where(
            User.id == payload.client_id,
            User.role == "client",
            User.account_status == "active",
        ).with_for_update()
    )

    client = result.scalar_one_or_none()

    if client is None:
        raise HTTPException(404, "Eligible client not found")

    doctor = await eligible_doctor(db, payload.doctor_id)

    if doctor is None:
        raise HTTPException(409, "Professional is not eligible")

    assignment = DoctorAssignment(
        client_id=client.id,
        doctor_id=doctor.id,
        assigned_by_uid=admin_uid,
        status="pending",
    )

    db.add(assignment)

    try:
        await db.flush()

        result = await db.execute(
            select(SupportRequest)
            .where(
                SupportRequest.client_id == client.id,
                SupportRequest.status == "pending",
            )
            .with_for_update()
        )

        support_request = result.scalar_one_or_none()

        if support_request is not None:
            support_request.assignment_id = assignment.id
            support_request.status = "assigned"

        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            409,
            "Client already has an open assignment",
        )

    await db.refresh(assignment)

    return assignment


@router.get(
    "/client",
    response_model=list[AssignmentResponse],
)
async def list_client_assignments(
    client: User = Depends(require_role(["client"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DoctorAssignment)
        .where(DoctorAssignment.client_id == client.id)
        .order_by(DoctorAssignment.created_at.desc())
    )

    return result.scalars().all()


@router.get(
    "/doctor",
    response_model=list[AssignmentResponse],
)
async def list_doctor_assignments(
    doctor: User = Depends(require_verified_doctor()),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DoctorAssignment)
        .join(User, User.id == DoctorAssignment.client_id)
        .where(
            DoctorAssignment.doctor_id == doctor.id,
            DoctorAssignment.status == "active",
            DoctorAssignment.consented_at.is_not(None),
            User.role == "client",
            User.account_status == "active",
        )
        .order_by(DoctorAssignment.created_at.desc())
    )

    return result.scalars().all()



async def close_linked_support_request(
    db,
    assignment_id,
    final_status,
):
    result = await db.execute(
        select(SupportRequest)
        .where(
            SupportRequest.assignment_id == assignment_id,
            SupportRequest.status == "assigned",
        )
        .with_for_update()
    )

    support_request = result.scalar_one_or_none()

    if support_request is not None:
        support_request.status = final_status
        support_request.ended_at = datetime.now(timezone.utc)


async def get_client_assignment(db, assignment_id, client_id):
    result = await db.execute(
        select(DoctorAssignment)
        .where(
            DoctorAssignment.id == assignment_id,
            DoctorAssignment.client_id == client_id,
        )
        .with_for_update()
    )

    assignment = result.scalar_one_or_none()

    if assignment is None:
        raise HTTPException(404, "Assignment not found")

    return assignment


@router.post(
    "/{assignment_id}/accept",
    response_model=AssignmentResponse,
)
async def accept_assignment(
    assignment_id: UUID,
    client: User = Depends(require_role(["client"])),
    db: AsyncSession = Depends(get_db),
):
    assignment = await get_client_assignment(
        db, assignment_id, client.id
    )

    if assignment.status != "pending":
        raise HTTPException(409, "Assignment is not pending")

    doctor = await eligible_doctor(
        db, assignment.doctor_id
    )

    if doctor is None:
        raise HTTPException(
            409,
            "Assigned professional is no longer eligible",
        )

    assignment.status = "active"
    assignment.consented_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(assignment)

    return assignment


@router.post(
    "/{assignment_id}/revoke",
    response_model=AssignmentResponse,
)
async def revoke_assignment(
    assignment_id: UUID,
    client: User = Depends(require_role(["client"])),
    db: AsyncSession = Depends(get_db),
):
    assignment = await get_client_assignment(
        db, assignment_id, client.id
    )

    if assignment.status not in {"pending", "active"}:
        raise HTTPException(409, "Assignment has already ended")

    assignment.status = "revoked"
    assignment.ended_at = datetime.now(timezone.utc)

    await close_linked_support_request(
        db,
        assignment.id,
        "cancelled",
    )

    await db.commit()
    await db.refresh(assignment)

    return assignment


@router.post(
    "/{assignment_id}/complete",
    response_model=AssignmentResponse,
)
async def complete_assignment(
    assignment_id: UUID,
    doctor: User = Depends(require_verified_doctor()),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DoctorAssignment)
        .where(
            DoctorAssignment.id == assignment_id,
            DoctorAssignment.doctor_id == doctor.id,
        )
        .with_for_update()
    )

    assignment = result.scalar_one_or_none()

    if assignment is None:
        raise HTTPException(404, "Assignment not found")

    if assignment.status != "active":
        raise HTTPException(409, "Assignment is not active")

    if await eligible_doctor(db, doctor.id) is None:
        raise HTTPException(403, "Professional access withdrawn")

    assignment.status = "completed"
    assignment.ended_at = datetime.now(timezone.utc)

    await close_linked_support_request(
        db,
        assignment.id,
        "closed",
    )

    await db.commit()
    await db.refresh(assignment)

    return assignment
