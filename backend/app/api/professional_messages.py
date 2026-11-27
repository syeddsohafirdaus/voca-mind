"""Consent-protected professional messaging."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_db
from app.models.user import User
from app.models.doctor_application import DoctorApplication
from app.models.doctor_assignment import DoctorAssignment
from app.models.professional_message import ProfessionalMessage


router = APIRouter()


class MessageRequest(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    content: str = Field(min_length=1, max_length=5000)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assignment_id: UUID
    sender_id: UUID
    sender_role: str
    content: str
    created_at: datetime
    read_at: datetime | None


async def authorize_assignment(db, assignment_id, user):
    result = await db.execute(
        select(DoctorAssignment)
        .where(DoctorAssignment.id == assignment_id)
        .with_for_update()
    )

    assignment = result.scalar_one_or_none()

    if assignment is None:
        raise HTTPException(404, "Assignment not found")

    is_client = (
        user.role == "client"
        and user.id == assignment.client_id
    )

    is_doctor = (
        user.role == "doctor"
        and user.id == assignment.doctor_id
    )

    if not (is_client or is_doctor):
        raise HTTPException(404, "Assignment not found")

    if (
        assignment.status != "active"
        or assignment.consented_at is None
    ):
        raise HTTPException(
            403,
            "Active client consent is required",
        )

    result = await db.execute(
        select(User)
        .where(User.id == assignment.client_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    client = result.scalar_one_or_none()

    if (
        client is None
        or client.role != "client"
        or client.account_status != "active"
    ):
        raise HTTPException(403, "Client access unavailable")

    result = await db.execute(
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

    if result.scalar_one_or_none() is None:
        raise HTTPException(
            403,
            "Professional access unavailable",
        )

    return assignment


@router.post(
    "/{assignment_id}/messages",
    response_model=MessageResponse,
    status_code=201,
)
async def send_message(
    assignment_id: UUID,
    payload: MessageRequest,
    user: User = Depends(require_role(["client", "doctor"])),
    db: AsyncSession = Depends(get_db),
):
    assignment = await authorize_assignment(
        db, assignment_id, user
    )

    message = ProfessionalMessage(
        assignment_id=assignment.id,
        sender_id=user.id,
        sender_role=user.role,
        content=payload.content,
    )

    db.add(message)

    await db.commit()
    await db.refresh(message)

    return message


@router.get(
    "/{assignment_id}/messages",
    response_model=list[MessageResponse],
)
async def list_messages(
    assignment_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_role(["client", "doctor"])),
    db: AsyncSession = Depends(get_db),
):
    await authorize_assignment(
        db, assignment_id, user
    )

    result = await db.execute(
        select(ProfessionalMessage)
        .where(
            ProfessionalMessage.assignment_id == assignment_id
        )
        .order_by(
            ProfessionalMessage.created_at.desc(),
            ProfessionalMessage.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return result.scalars().all()


@router.get("/{assignment_id}/unread")
async def unread_messages(
    assignment_id: UUID,
    user: User = Depends(require_role(["client", "doctor"])),
    db: AsyncSession = Depends(get_db),
):
    await authorize_assignment(
        db, assignment_id, user
    )

    result = await db.execute(
        select(func.count(ProfessionalMessage.id))
        .where(
            ProfessionalMessage.assignment_id == assignment_id,
            ProfessionalMessage.sender_id != user.id,
            ProfessionalMessage.read_at.is_(None),
        )
    )

    return {"unread_count": result.scalar_one()}


@router.post("/{assignment_id}/messages/{message_id}/read")
async def mark_message_read(
    assignment_id: UUID,
    message_id: UUID,
    user: User = Depends(require_role(["client", "doctor"])),
    db: AsyncSession = Depends(get_db),
):
    await authorize_assignment(
        db, assignment_id, user
    )

    result = await db.execute(
        select(ProfessionalMessage)
        .where(
            ProfessionalMessage.id == message_id,
            ProfessionalMessage.assignment_id == assignment_id,
            ProfessionalMessage.sender_id != user.id,
        )
        .with_for_update()
    )

    message = result.scalar_one_or_none()

    if message is None:
        raise HTTPException(404, "Message not found")

    if message.read_at is None:
        message.read_at = datetime.now(timezone.utc)

    await db.commit()

    return {"status": "read"}
