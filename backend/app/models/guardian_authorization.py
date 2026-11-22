import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class GuardianAuthorization(Base):
    """Explicit, revocable Client-to-Guardian authorization."""

    __tablename__ = "guardian_authorizations"

    __table_args__ = (
        UniqueConstraint(
            "client_id",
            "guardian_id",
            name="uq_guardian_authorizations_client_guardian",
        ),
        CheckConstraint(
            "client_id <> guardian_id",
            name="ck_guardian_authorizations_distinct_users",
        ),
        CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_guardian_authorizations_status",
        ),
        CheckConstraint(
            "status <> 'revoked' OR revoked_at IS NOT NULL",
            name="ck_guardian_authorizations_revocation_timestamp",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    guardian_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
    )

    consented_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    client: Mapped["User"] = relationship(
        "User",
        foreign_keys=[client_id],
        lazy="selectin",
    )

    guardian: Mapped["User"] = relationship(
        "User",
        foreign_keys=[guardian_id],
        lazy="selectin",
    )
