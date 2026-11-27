"""Add guardian consent version identifiers."""

import uuid
import sqlalchemy as sa
from alembic import op

revision = "014_guardian_consent_version"
down_revision = "013_guardian_wellbeing"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "guardian_authorizations",
        sa.Column(
            "consent_version",
            sa.Uuid(),
            nullable=True,
        ),
    )

    table = sa.table(
        "guardian_authorizations",
        sa.column("id", sa.Uuid()),
        sa.column("consent_version", sa.Uuid()),
    )

    connection = op.get_bind()

    ids = connection.execute(
        sa.select(table.c.id)
    ).scalars().all()

    for authorization_id in ids:
        connection.execute(
            table.update()
            .where(table.c.id == authorization_id)
            .values(consent_version=uuid.uuid4())
        )

    op.alter_column(
        "guardian_authorizations",
        "consent_version",
        nullable=False,
    )


def downgrade():
    op.drop_column(
        "guardian_authorizations",
        "consent_version",
    )
