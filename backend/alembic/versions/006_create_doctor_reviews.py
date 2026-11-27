"""Create professional verification audit records.

Revision ID: 006_doctor_reviews
Revises: 005_guardian_auth
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "006_doctor_reviews"
down_revision = "005_guardian_auth"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "doctor_reviews",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),

        sa.Column(
            "application_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "doctor_applications.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),

        sa.Column(
            "reviewer_uid",
            sa.String(128),
            nullable=False,
        ),

        sa.Column(
            "decision",
            sa.String(20),
            nullable=False,
        ),

        sa.Column(
            "previous_status",
            sa.String(20),
            nullable=False,
        ),

        sa.Column(
            "reason",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.CheckConstraint(
            "decision IN ('approved', 'rejected', 'suspended')",
            name="ck_doctor_reviews_decision",
        ),
    )

    op.create_index(
        "ix_doctor_reviews_application_id",
        "doctor_reviews",
        ["application_id"],
    )


def downgrade():
    op.drop_index(
        "ix_doctor_reviews_application_id",
        table_name="doctor_reviews",
    )

    op.drop_table("doctor_reviews")
