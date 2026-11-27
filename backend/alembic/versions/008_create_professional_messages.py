"""Create professional messaging records."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "008_professional_messages"
down_revision = "007_doctor_assignments"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "professional_messages",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),

        sa.Column(
            "assignment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "doctor_assignments.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),

        sa.Column(
            "sender_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "users.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),

        sa.Column(
            "sender_role",
            sa.String(20),
            nullable=False,
        ),

        sa.Column(
            "content",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),

        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.CheckConstraint(
            "sender_role IN ('client', 'doctor')",
            name="ck_professional_message_sender_role",
        ),

        sa.CheckConstraint(
            "length(trim(content)) BETWEEN 1 AND 5000",
            name="ck_professional_message_content",
        ),
    )

    op.create_index(
        "ix_professional_messages_assignment_created",
        "professional_messages",
        ["assignment_id", "created_at"],
    )


def downgrade():
    op.drop_table("professional_messages")
