"""Client-controlled wellbeing updates."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GuardianWellbeing(Base):
    __tablename__ = "guardian_wellbeing"

    __table_args__ = (
        CheckConstraint(
            "wellbeing IN ('doing_well', 'managing', 'would_like_support')",
            name="ck_guardian_wellbeing_status",
        ),
    )

    authorization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("guardian_authorizations.id", ondelete="CASCADE"),
        primary_key=True,
    )

    wellbeing: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    shared_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
