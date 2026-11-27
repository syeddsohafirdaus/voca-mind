"""Create consent-based professional assignments."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "007_doctor_assignments"
down_revision = "006_doctor_reviews"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "doctor_assignments",

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
            "doctor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),

        sa.Column(
            "assigned_by_uid",
            sa.String(128),
            nullable=False,
        ),

        sa.Column(
            "status",
            sa.String(20),
            server_default="pending",
            nullable=False,
        ),

        sa.Column(
            "consented_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "ended_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.CheckConstraint(
            "client_id <> doctor_id",
            name="ck_assignment_distinct_users",
        ),

        sa.CheckConstraint(
            "status IN ('pending', 'active', 'revoked', 'completed')",
            name="ck_assignment_status",
        ),

        sa.CheckConstraint(
            "status NOT IN ('active', 'completed') "
            "OR consented_at IS NOT NULL",
            name="ck_assignment_consent",
        ),

        sa.CheckConstraint(
            "status NOT IN ('revoked', 'completed') "
            "OR ended_at IS NOT NULL",
            name="ck_assignment_ended",
        ),
    )

    op.create_index(
        "ix_doctor_assignments_client_id",
        "doctor_assignments",
        ["client_id"],
    )

    op.create_index(
        "ix_doctor_assignments_doctor_id",
        "doctor_assignments",
        ["doctor_id"],
    )

    op.create_index(
        "uq_client_open_assignment",
        "doctor_assignments",
        ["client_id"],
        unique=True,
        postgresql_where=sa.text(
            "status IN ('pending', 'active')"
        ),
    )


def downgrade():
    op.drop_table("doctor_assignments")
