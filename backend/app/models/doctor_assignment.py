"""Consent-based professional assignments."""

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


class DoctorAssignment(Base):
    __tablename__ = "doctor_assignments"

    __table_args__ = (
        CheckConstraint(
            "client_id <> doctor_id",
            name="ck_assignment_distinct_users",
        ),
        CheckConstraint(
            "status IN ('pending', 'active', 'revoked', 'completed')",
            name="ck_assignment_status",
        ),
        CheckConstraint(
            "status NOT IN ('active', 'completed') "
            "OR consented_at IS NOT NULL",
            name="ck_assignment_consent",
        ),
        CheckConstraint(
            "status NOT IN ('revoked', 'completed') "
            "OR ended_at IS NOT NULL",
            name="ck_assignment_ended",
        ),
        Index(
            "uq_client_open_assignment",
            "client_id",
            unique=True,
            postgresql_where=text(
                "status IN ('pending', 'active')"
            ),
            sqlite_where=text(
                "status IN ('pending', 'active')"
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

    doctor_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    assigned_by_uid: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="pending",
        nullable=False,
    )

    consented_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
