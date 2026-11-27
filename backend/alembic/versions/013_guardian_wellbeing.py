"""Add consent-controlled guardian wellbeing updates."""

from alembic import op
import sqlalchemy as sa

revision = "013_guardian_wellbeing"
down_revision = "012_takeover_notifications"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "guardian_wellbeing",
        sa.Column(
            "authorization_id",
            sa.Uuid(),
            sa.ForeignKey(
                "guardian_authorizations.id",
                ondelete="CASCADE",
            ),
            primary_key=True,
        ),
        sa.Column("wellbeing", sa.String(30), nullable=False),
        sa.Column(
            "shared_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.CheckConstraint(
            "wellbeing IN ('doing_well', 'managing', 'would_like_support')",
            name="ck_guardian_wellbeing_status",
        ),
    )


def downgrade():
    op.drop_table("guardian_wellbeing")
