"""Consent-controlled human takeover endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    require_role,
    require_verified_doctor,
)
from app.database import get_db
from app.models.user import User
from app.models.doctor_application import DoctorApplication
from app.models.doctor_assignment import DoctorAssignment
from app.models.human_takeover import HumanTakeover
from app.schemas.takeover import (
    TakeoverRequest,
    TakeoverResponse,
)
from app.services.human_takeover_service import (
    TakeoverConflict,
    get_open_takeover,
    request_takeover,
    accept_takeover,
    cancel_takeover,
    end_takeover,
)

from app.services.notification_service import create_notification


router = APIRouter()

get_client = require_role(["client"])
get_doctor = require_verified_doctor()
get_participant = require_role(["client", "doctor"])


async def lock_assignment(
    db: AsyncSession,
    assignment_id: UUID,
    user: User,
) -> DoctorAssignment:

    owner_column = (
        DoctorAssignment.client_id
        if user.role == "client"
        else DoctorAssignment.doctor_id
    )

    result = await db.execute(
        select(DoctorAssignment)
        .where(
            DoctorAssignment.id == assignment_id,
            owner_column == user.id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    assignment = result.scalar_one_or_none()

    if assignment is None:
        raise HTTPException(404, "Assignment not found")

    return assignment


async def require_eligible_assignment(
    db: AsyncSession,
    assignment: DoctorAssignment,
):

    if (
        assignment.status != "active"
        or assignment.consented_at is None
        or assignment.ended_at is not None
    ):
        raise HTTPException(
            409, "An active consented assignment is required"
        )

    client = (
        await db.execute(
            select(User)
            .where(
                User.id == assignment.client_id,
                User.role == "client",
                User.account_status == "active",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()

    if client is None:
        raise HTTPException(403, "Client is not eligible")

    doctor = (
        await db.execute(
            select(User)
            .join(
                DoctorApplication,
                DoctorApplication.user_id == User.id,
            )
            .where(
                User.id == assignment.doctor_id,
                User.role == "doctor",
                User.account_status == "active",
                User.is_verified.is_(True),
                DoctorApplication.status == "approved",
                DoctorApplication.reviewed_at.is_not(None),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()

    if doctor is None:
        raise HTTPException(
            403, "Professional is not eligible"
        )


async def require_active_client(db, client_id):
    result = await db.execute(
        select(User)
        .where(
            User.id == client_id,
            User.role == "client",
            User.account_status == "active",
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    if result.scalar_one_or_none() is None:
        raise HTTPException(403, "Client is not eligible")


async def require_open_takeover(db, assignment_id, takeover_id: UUID):
    takeover = await get_open_takeover(
        db, assignment_id
    )

    if takeover is None:
        raise HTTPException(
            409, "No open takeover session"
        )

    if takeover.id != takeover_id:
        raise HTTPException(
            409, "Takeover session has changed"
        )

    return takeover


async def persist_takeover(db, takeover):
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            409, "Takeover state conflict"
        )

    await db.refresh(takeover)
    return takeover


@router.post(
    "/{assignment_id}/request",
    response_model=TakeoverResponse,
    status_code=201,
)
async def create_takeover_request(
    assignment_id: UUID,
    payload: TakeoverRequest,
    current_user: User = Depends(get_client),
    db: AsyncSession = Depends(get_db),
):
    assignment = await lock_assignment(
        db, assignment_id, current_user
    )

    await require_eligible_assignment(db, assignment)

    try:
        takeover = await request_takeover(
            db, assignment.id
        )
    except (TakeoverConflict, IntegrityError):
        await db.rollback()
        raise HTTPException(
            409, "An open takeover already exists"
        )

    await create_notification(
        db,
        recipient_id=assignment.doctor_id,
        event_type="takeover_requested",
        reference_id=takeover.id,
    )

    return await persist_takeover(db, takeover)


@router.post(
    "/{assignment_id}/accept",
    response_model=TakeoverResponse,
)
async def accept_takeover_request(
    assignment_id: UUID,
    takeover_id: UUID,
    current_user: User = Depends(get_doctor),
    db: AsyncSession = Depends(get_db),
):
    assignment = await lock_assignment(
        db, assignment_id, current_user
    )

    await require_eligible_assignment(db, assignment)

    takeover = await require_open_takeover(
        db, assignment.id, takeover_id
    )

    try:
        await accept_takeover(db, takeover)
    except TakeoverConflict:
        raise HTTPException(
            409, "Takeover request is not pending"
        )

    await create_notification(
        db,
        recipient_id=assignment.client_id,
        event_type="takeover_accepted",
        reference_id=takeover.id,
    )

    return await persist_takeover(db, takeover)


@router.post(
    "/{assignment_id}/cancel",
    response_model=TakeoverResponse,
)
async def cancel_takeover_request(
    assignment_id: UUID,
    takeover_id: UUID,
    current_user: User = Depends(get_client),
    db: AsyncSession = Depends(get_db),
):
    assignment = await lock_assignment(
        db, assignment_id, current_user
    )

    await require_active_client(db, assignment.client_id)

    takeover = await require_open_takeover(
        db, assignment.id, takeover_id
    )

    try:
        await cancel_takeover(db, takeover)
    except TakeoverConflict:
        raise HTTPException(
            409, "Only pending requests can be cancelled"
        )

    await create_notification(
        db,
        recipient_id=assignment.doctor_id,
        event_type="takeover_cancelled",
        reference_id=takeover.id,
    )

    return await persist_takeover(db, takeover)




@router.post(
    "/{assignment_id}/end",
    response_model=TakeoverResponse,
)
async def terminate_takeover(
    assignment_id: UUID,
    takeover_id: UUID,
    current_user: User = Depends(get_participant),
    db: AsyncSession = Depends(get_db),
):
    assignment = await lock_assignment(
        db, assignment_id, current_user
    )

    if current_user.role == "doctor":
        await require_eligible_assignment(
            db, assignment
        )

    await require_active_client(db, assignment.client_id)

    takeover = await require_open_takeover(
        db, assignment.id, takeover_id
    )

    try:
        await end_takeover(db, takeover)
    except TakeoverConflict:
        raise HTTPException(
            409, "Takeover session is not active"
        )

    await create_notification(
        db,
        recipient_id=(assignment.doctor_id if current_user.role == 'client' else assignment.client_id),
        event_type="takeover_ended",
        reference_id=takeover.id,
    )

    return await persist_takeover(db, takeover)


@router.get(
    "/client",
    response_model=list[TakeoverResponse],
)
async def list_client_takeovers(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_client),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HumanTakeover)
        .join(
            DoctorAssignment,
            DoctorAssignment.id
            == HumanTakeover.assignment_id,
        )
        .where(
            DoctorAssignment.client_id
            == current_user.id
        )
        .order_by(
            HumanTakeover.created_at.desc(),
            HumanTakeover.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return list(result.scalars().all())


@router.get(
    "/doctor",
    response_model=list[TakeoverResponse],
)
async def list_doctor_takeovers(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_doctor),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(HumanTakeover)
        .join(
            DoctorAssignment,
            DoctorAssignment.id
            == HumanTakeover.assignment_id,
        )
        .join(
            User,
            User.id == DoctorAssignment.client_id,
        )
        .where(
            DoctorAssignment.doctor_id
            == current_user.id,
            DoctorAssignment.status == "active",
            DoctorAssignment.consented_at.is_not(None),
            DoctorAssignment.ended_at.is_(None),
            User.role == "client",
            User.account_status == "active",
        )
        .order_by(
            HumanTakeover.created_at.desc(),
            HumanTakeover.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return list(result.scalars().all())
