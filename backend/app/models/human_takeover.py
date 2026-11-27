"""Consent-based human takeover sessions."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class HumanTakeover(Base):
    __tablename__ = "human_takeovers"

    __table_args__ = (
        CheckConstraint(
            "status IN ('requested', 'active', "
            "'cancelled', 'ended')",
            name="ck_takeover_status",
        ),
        CheckConstraint(
            "status NOT IN ('active', 'ended') "
            "OR accepted_at IS NOT NULL",
            name="ck_takeover_acceptance",
        ),
        CheckConstraint(
            "status NOT IN ('requested', 'cancelled') "
            "OR accepted_at IS NULL",
            name="ck_takeover_pending_acceptance",
        ),
        CheckConstraint(
            "(status IN ('cancelled', 'ended') "
            "AND ended_at IS NOT NULL) OR "
            "(status IN ('requested', 'active') "
            "AND ended_at IS NULL)",
            name="ck_takeover_closure",
        ),
        Index(
            "uq_assignment_open_takeover",
            "assignment_id",
            unique=True,
            postgresql_where=text(
                "status IN ('requested', 'active')"
            ),
            sqlite_where=text(
                "status IN ('requested', 'active')"
            ),
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
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="requested",
        server_default="requested",
        nullable=False,
    )

    consented_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    accepted_at: Mapped[datetime | None] = mapped_column(
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
