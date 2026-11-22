
"""Add three-role authentication fields to users.

Revision ID: 003_add_user_roles
Revises: 002_add_firebase_uid
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003_add_user_roles"
down_revision: Union[str, None] = "002_add_firebase_uid"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "role",
            sa.String(length=20),
            nullable=False,
            server_default="client",
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "display_name",
            sa.String(length=150),
            nullable=True,
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "date_of_birth",
            sa.Date(),
            nullable=True,
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "account_status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "is_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

    op.create_check_constraint(
        "ck_users_role",
        "users",
        "role IN ('client', 'doctor', 'guardian')",
    )

    op.create_check_constraint(
        "ck_users_account_status",
        "users",
        "account_status IN ('pending', 'active', 'suspended')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_users_account_status",
        "users",
        type_="check",
    )

    op.drop_constraint(
        "ck_users_role",
        "users",
        type_="check",
    )

    op.drop_column("users", "is_verified")
    op.drop_column("users", "account_status")
    op.drop_column("users", "date_of_birth")
    op.drop_column("users", "display_name")
    op.drop_column("users", "role")
