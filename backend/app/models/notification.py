"""Privacy-preserving in-app notifications."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime, ForeignKey, String,
    CheckConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Notification(Base):
    __tablename__ = "notifications"

    __table_args__ = (
        CheckConstraint(
            "event_type IN ("
            "'support_requested', "
            "'assignment_proposed', "
            "'assignment_accepted', "
            "'assignment_revoked', "
            "'assignment_completed', "
            "'professional_message', 'takeover_requested', 'takeover_accepted', 'takeover_cancelled', 'takeover_ended')",
            name="ck_notification_event_type",
        ),
        Index(
            "ix_notification_recipient_created",
            "recipient_id", "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    recipient_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
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
