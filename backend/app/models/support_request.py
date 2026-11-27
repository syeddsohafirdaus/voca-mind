"""Consent-based requests for professional support."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SupportRequest(Base):

    __tablename__ = "support_requests"

    __table_args__ = (
        CheckConstraint(
            "source IN ('client', 'ai_suggestion')",
            name="ck_support_request_source",
        ),
        CheckConstraint(
            "status IN ('pending', 'assigned', 'cancelled', 'closed')",
            name="ck_support_request_status",
        ),
        CheckConstraint(
            "status != 'assigned' OR assignment_id IS NOT NULL",
            name="ck_support_request_assignment",
        ),
        CheckConstraint(
            "status NOT IN ('cancelled', 'closed') OR ended_at IS NOT NULL",
            name="ck_support_request_ended",
        ),
        Index(
            "uq_client_open_support_request",
            "client_id",
            unique=True,
            postgresql_where=text(
                "status IN ('pending', 'assigned')"
            ),
            sqlite_where=text(
                "status IN ('pending', 'assigned')"
            ),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    assignment_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "doctor_assignments.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        unique=True,
    )

    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="client",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
    )

    consented_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
