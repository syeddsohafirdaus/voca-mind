"""Add human takeover notification events."""

from alembic import op

revision = "012_takeover_notifications"
down_revision = "011_human_takeovers"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(
        'ck_notification_event_type',
        "notifications",
        type_="check",
    )
    op.create_check_constraint(
        'ck_notification_event_type',
        "notifications",
        "event_type IN ('support_requested', 'assignment_proposed', 'assignment_accepted', 'assignment_revoked', 'assignment_completed', 'professional_message', 'takeover_requested', 'takeover_accepted', 'takeover_cancelled', 'takeover_ended')",
    )


def downgrade():
    op.drop_constraint(
        'ck_notification_event_type',
        "notifications",
        type_="check",
    )
    op.create_check_constraint(
        'ck_notification_event_type',
        "notifications",
        "event_type IN ('support_requested', 'assignment_proposed', 'assignment_accepted', 'assignment_revoked', 'assignment_completed', 'professional_message')",
    )
