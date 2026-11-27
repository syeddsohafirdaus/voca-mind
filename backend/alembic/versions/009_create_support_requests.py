"""Create consent-based professional support requests."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "009_support_requests"
down_revision = "008_professional_messages"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "support_requests",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),

        sa.Column(
            "client_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),

        sa.Column(
            "assignment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "doctor_assignments.id",
                ondelete="RESTRICT",
            ),
            nullable=True,
            unique=True,
        ),

        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),

        sa.Column(
            "consented_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.Column(
            "ended_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.CheckConstraint(
            "source IN ('client', 'ai_suggestion')",
            name="ck_support_request_source",
        ),

        sa.CheckConstraint(
            "status IN ('pending', 'assigned', 'cancelled', 'closed')",
            name="ck_support_request_status",
        ),

        sa.CheckConstraint(
            "status != 'assigned' OR assignment_id IS NOT NULL",
            name="ck_support_request_assignment",
        ),

        sa.CheckConstraint(
            "status NOT IN ('cancelled', 'closed') OR ended_at IS NOT NULL",
            name="ck_support_request_ended",
        ),
    )

    op.create_index(
        "ix_support_requests_client_id",
        "support_requests",
        ["client_id"],
    )

    op.create_index(
        "uq_client_open_support_request",
        "support_requests",
        ["client_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('pending', 'assigned')"
        ),
    )


def downgrade():
    op.drop_table("support_requests")
