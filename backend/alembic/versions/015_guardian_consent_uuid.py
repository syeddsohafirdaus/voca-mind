"""Align guardian consent version with UUID model."""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "015_guardian_consent_uuid"
down_revision = "014_guardian_consent_version"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()

    columns = sa.inspect(connection).get_columns(
        "guardian_authorizations"
    )

    column = next(
        c for c in columns
        if c["name"] == "consent_version"
    )

    if isinstance(column["type"], sa.Uuid):
        return

    if not isinstance(column["type"], sa.Integer):
        raise RuntimeError(
            "Unexpected consent_version datatype"
        )

    op.execute(
        "LOCK TABLE guardian_authorizations "
        "IN ACCESS EXCLUSIVE MODE"
    )

    op.add_column(
        "guardian_authorizations",
        sa.Column(
            "consent_version_uuid",
            sa.Uuid(),
            nullable=True,
        ),
    )

    table = sa.table(
        "guardian_authorizations",
        sa.column("id", sa.Uuid()),
        sa.column("consent_version_uuid", sa.Uuid()),
    )

    ids = connection.execute(
        sa.select(table.c.id)
    ).scalars().all()

    for authorization_id in ids:
        connection.execute(
            table.update()
            .where(table.c.id == authorization_id)
            .values(consent_version_uuid=uuid.uuid4())
        )

    op.alter_column(
        "guardian_authorizations",
        "consent_version_uuid",
        nullable=False,
    )

    op.drop_column(
        "guardian_authorizations",
        "consent_version",
    )

    op.alter_column(
        "guardian_authorizations",
        "consent_version_uuid",
        new_column_name="consent_version",
    )


def downgrade():
    raise RuntimeError(
        "Automatic downgrade is disabled because "
        "previous consent versions cannot be recovered."
    )
