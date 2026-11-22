
import uuid
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, DateTime, String, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


if TYPE_CHECKING:
    from app.models.conversation import Conversation


class User(Base):
    """Voca Mind user model supporting clients, doctors, and guardians."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    firebase_uid: Mapped[Optional[str]] = mapped_column(
        String(128),
        unique=True,
        index=True,
        nullable=True,
    )

    # Account role: client, doctor, or guardian.
    # New accounts default to client.
    # Doctor access requires separate verification and authorization.
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="client",
        server_default="client",
    )

    display_name: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
    )

    # Used for client age eligibility (18-30 at registration).
    # Eligibility enforcement will be implemented separately.
    date_of_birth: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )

    # Allowed values: pending, active, suspended.
    account_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        server_default="active",
    )

    # Professional verification flag.
    # This field alone must never authorize doctor access.
    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Preserve existing user conversation history.
    conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
