"""Create guardian authorizations table.

Revision ID: 005_guardian_auth
Revises: 004_create_doctor_applications
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "005_guardian_auth"
down_revision: Union[str, None] = "004_create_doctor_applications"

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the guardian authorizations table."""

    op.create_table(
        "guardian_authorizations",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),

        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),

        sa.Column(
            "guardian_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),

        sa.Column(
            "consented_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.UniqueConstraint(
            "client_id",
            "guardian_id",
            name="uq_guardian_authorizations_client_guardian",
        ),

        sa.CheckConstraint(
            "client_id <> guardian_id",
            name="ck_guardian_authorizations_distinct_users",
        ),

        sa.CheckConstraint(
            "status IN ('active', 'revoked')",
            name="ck_guardian_authorizations_status",
        ),

        sa.CheckConstraint(
            "status <> 'revoked' OR revoked_at IS NOT NULL",
            name="ck_guardian_authorizations_revocation_timestamp",
        ),
    )

    op.create_index(
        "ix_guardian_authorizations_client_id",
        "guardian_authorizations",
        ["client_id"],
    )

    op.create_index(
        "ix_guardian_authorizations_guardian_id",
        "guardian_authorizations",
        ["guardian_id"],
    )


def downgrade() -> None:
    """Remove the guardian authorizations table."""

    op.drop_index(
        "ix_guardian_authorizations_guardian_id",
        table_name="guardian_authorizations",
    )

    op.drop_index(
        "ix_guardian_authorizations_client_id",
        table_name="guardian_authorizations",
    )

    op.drop_table("guardian_authorizations")
