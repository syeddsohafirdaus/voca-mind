
"""Create doctor applications table.

Revision ID: 004_create_doctor_applications
Revises: 003_add_user_roles
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "004_create_doctor_applications"
down_revision: Union[str, None] = "003_add_user_roles"

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the doctor applications table."""

    op.create_table(
        "doctor_applications",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),

        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),

        sa.Column(
            "registration_number",
            sa.String(length=100),
            nullable=False,
        ),

        sa.Column(
            "licensing_authority",
            sa.String(length=150),
            nullable=False,
        ),

        sa.Column(
            "specialization",
            sa.String(length=150),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_doctor_applications_status",
        ),

        sa.UniqueConstraint(
            "user_id",
            name="uq_doctor_applications_user_id",
        ),
    )

    op.create_index(
        "ix_doctor_applications_user_id",
        "doctor_applications",
        ["user_id"],
    )


def downgrade() -> None:
    """Remove the doctor applications table."""

    op.drop_index(
        "ix_doctor_applications_user_id",
        table_name="doctor_applications",
    )

    op.drop_table("doctor_applications")
