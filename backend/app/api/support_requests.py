"""Consent-based professional support requests."""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.admin import require_platform_admin
from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import User
from app.models.support_request import SupportRequest
from app.services.notification_service import create_notification
from app.models.doctor_assignment import DoctorAssignment


router = APIRouter()


class SupportRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal["client", "ai_suggestion"] = "client"
    consent: Literal[True]


class SupportRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    client_id: UUID
    assignment_id: UUID | None
    source: str
    status: str
    consented_at: datetime
    created_at: datetime
    ended_at: datetime | None


@router.post(
    "/request",
    response_model=SupportRequestResponse,
    status_code=201,
)
async def create_support_request(
    payload: SupportRequestCreate,
    client: User = Depends(require_role(["client"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .where(
            User.id == client.id,
            User.role == "client",
            User.account_status == "active",
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    if result.scalar_one_or_none() is None:
        raise HTTPException(403, "Client access unavailable")

    result = await db.execute(
        select(DoctorAssignment.id).where(
            DoctorAssignment.client_id == client.id,
            DoctorAssignment.status.in_(["pending", "active"]),
        )
    )

    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            409,
            "Client already has an open professional assignment",
        )

    request = SupportRequest(
        client_id=client.id,
        source=payload.source,
        status="pending",
        consented_at=datetime.now(timezone.utc),
    )

    db.add(request)

    try:
        await db.flush()

        await create_notification(
            db,
            recipient_id=request.client_id,
            event_type="support_requested",
            reference_id=request.id,
        )

        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            409,
            "An open support request already exists",
        )

    await db.refresh(request)

    return request


@router.get(
    "/client",
    response_model=list[SupportRequestResponse],
)
async def list_client_requests(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    client: User = Depends(require_role(["client"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SupportRequest)
        .where(SupportRequest.client_id == client.id)
        .order_by(
            SupportRequest.created_at.desc(),
            SupportRequest.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return result.scalars().all()


@router.get(
    "/admin",
    response_model=list[SupportRequestResponse],
)
async def list_admin_requests(
    status: Literal[
        "pending", "assigned", "cancelled", "closed"
    ] = "pending",
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    admin_uid: str = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SupportRequest)
        .where(SupportRequest.status == status)
        .order_by(
            SupportRequest.created_at.asc(),
            SupportRequest.id.asc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return result.scalars().all()


@router.post(
    "/{request_id}/cancel",
    response_model=SupportRequestResponse,
)
async def cancel_support_request(
    request_id: UUID,
    client: User = Depends(require_role(["client"])),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SupportRequest)
        .where(
            SupportRequest.id == request_id,
            SupportRequest.client_id == client.id,
        )
        .with_for_update()
    )

    request = result.scalar_one_or_none()

    if request is None:
        raise HTTPException(404, "Support request not found")

    if request.status != "pending":
        raise HTTPException(
            409,
            "Only pending requests can be cancelled here",
        )

    request.status = "cancelled"
    request.ended_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(request)

    return request
