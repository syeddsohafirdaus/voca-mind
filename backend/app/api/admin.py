"""Restricted professional verification endpoints."""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.admin import require_platform_admin
from app.database import get_db
from app.models.user import User
from app.models.doctor_application import DoctorApplication
from app.models.doctor_review import DoctorReview


router = APIRouter()


class ReviewRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    reason: str = Field(min_length=10, max_length=1000)


class ApplicationResponse(BaseModel):
    id: UUID
    display_name: str | None
    registration_number: str
    licensing_authority: str
    specialization: str
    status: str
    account_status: str
    is_verified: bool
    created_at: datetime
    reviewed_at: datetime | None


def serialize_application(application, user):
    return ApplicationResponse(
        id=application.id,
        display_name=user.display_name,
        registration_number=application.registration_number,
        licensing_authority=application.licensing_authority,
        specialization=application.specialization,
        status=application.status,
        account_status=user.account_status,
        is_verified=user.is_verified,
        created_at=application.created_at,
        reviewed_at=application.reviewed_at,
    )


@router.get(
    "/doctor-applications",
    response_model=list[ApplicationResponse],
)
async def list_applications(
    status: Literal["pending", "approved", "rejected"] | None = None,
    admin_uid: str = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(DoctorApplication, User)
        .join(User, User.id == DoctorApplication.user_id)
        .where(User.role == "doctor")
        .order_by(DoctorApplication.created_at.desc())
    )

    if status is not None:
        query = query.where(
            DoctorApplication.status == status
        )

    result = await db.execute(query)

    return [
        serialize_application(application, user)
        for application, user in result.all()
    ]


@router.get(
    "/doctor-applications/{application_id}",
    response_model=ApplicationResponse,
)
async def get_application(
    application_id: UUID,
    admin_uid: str = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DoctorApplication, User)
        .join(User, User.id == DoctorApplication.user_id)
        .where(
            DoctorApplication.id == application_id,
            User.role == "doctor",
        )
    )

    row = result.one_or_none()

    if row is None:
        raise HTTPException(404, "Application not found")

    return serialize_application(*row)


@router.post(
    "/doctor-applications/{application_id}/{action}",
    response_model=ApplicationResponse,
)
async def review_application(
    application_id: UUID,
    action: Literal["approve", "reject", "suspend"],
    payload: ReviewRequest,
    admin_uid: str = Depends(require_platform_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DoctorApplication, User)
        .join(User, User.id == DoctorApplication.user_id)
        .where(
            DoctorApplication.id == application_id,
            User.role == "doctor",
        )
        .with_for_update()
    )

    row = result.one_or_none()

    if row is None:
        raise HTTPException(404, "Application not found")

    application, user = row

    if user.firebase_uid == admin_uid:
        raise HTTPException(
            403,
            "Administrators cannot review their own applications",
        )

    previous_status = application.status
    now = datetime.now(timezone.utc)

    if action in {"approve", "reject"}:
        if (
            application.status != "pending"
            or user.account_status != "pending"
            or user.is_verified
        ):
            raise HTTPException(
                409,
                "Application is not eligible for review",
            )

    if action == "approve":
        application.status = "approved"
        user.account_status = "active"
        user.is_verified = True
        decision = "approved"

    elif action == "reject":
        application.status = "rejected"
        user.account_status = "suspended"
        user.is_verified = False
        decision = "rejected"

    else:
        if (
            application.status != "approved"
            or user.account_status != "active"
            or not user.is_verified
        ):
            raise HTTPException(
                409,
                "Only active verified professionals can be suspended",
            )

        user.account_status = "suspended"
        user.is_verified = False
        decision = "suspended"

    application.reviewed_at = now

    review = DoctorReview(
        application_id=application.id,
        reviewer_uid=admin_uid,
        decision=decision,
        previous_status=previous_status,
        reason=payload.reason,
        created_at=now,
    )

    db.add(review)

    await db.commit()
    await db.refresh(application)
    await db.refresh(user)

    return serialize_application(application, user)
