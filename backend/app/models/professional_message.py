"""Messages exchanged within authorized professional assignments."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ProfessionalMessage(Base):

    __tablename__ = "professional_messages"

    __table_args__ = (
        CheckConstraint(
            "sender_role IN ('client', 'doctor')",
            name="ck_professional_message_sender_role",
        ),
        CheckConstraint(
            "length(trim(content)) BETWEEN 1 AND 5000",
            name="ck_professional_message_content",
        ),
        Index(
            "ix_professional_messages_assignment_created",
            "assignment_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "doctor_assignments.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    sender_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    sender_role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
