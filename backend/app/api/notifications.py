"""Recipient-only in-app notification endpoints."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    require_role,
)
from app.database import get_db
from app.models.user import User
from app.models.doctor_application import DoctorApplication
from app.services.notification_service import (
    list_notifications,
    count_unread_notifications,
    mark_notification_read,
)

router = APIRouter()


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    reference_id: UUID | None
    created_at: datetime
    read_at: datetime | None


class UnreadCountResponse(BaseModel):
    unread_count: int


async def notification_user(
    user: User = Depends(
        require_role(["client", "doctor"])
    ),
    db: AsyncSession = Depends(get_db),
):
    if user.role == "doctor":
        result = await db.execute(
            select(DoctorApplication.id).where(
                DoctorApplication.user_id == user.id,
                DoctorApplication.status == "approved",
                DoctorApplication.reviewed_at.is_not(None),
            )
        )

        if (
            not user.is_verified
            or result.scalar_one_or_none() is None
        ):
            raise HTTPException(
                403,
                "Professional access unavailable",
            )

    return user


@router.get(
    "",
    response_model=list[NotificationResponse],
)
async def get_notifications(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = False,
    user: User = Depends(notification_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_notifications(
        db,
        user.id,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
    )


@router.get(
    "/unread",
    response_model=UnreadCountResponse,
)
async def get_unread_count(
    user: User = Depends(notification_user),
    db: AsyncSession = Depends(get_db),
):
    count = await count_unread_notifications(
        db,
        user.id,
    )

    return UnreadCountResponse(
        unread_count=count,
    )


@router.post(
    "/{notification_id}/read",
    response_model=NotificationResponse,
)
async def read_notification(
    notification_id: UUID,
    user: User = Depends(notification_user),
    db: AsyncSession = Depends(get_db),
):
    notification = await mark_notification_read(
        db,
        recipient_id=user.id,
        notification_id=notification_id,
    )

    if notification is None:
        raise HTTPException(
            404,
            "Notification not found",
        )

    await db.commit()
    await db.refresh(notification)

    return notification
