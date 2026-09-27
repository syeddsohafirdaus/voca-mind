"""Add firebase_uid to users table

Revision ID: 002_add_firebase_uid
Revises: 001_initial_schema
Create Date: 2026-09-27 19:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_add_firebase_uid'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('firebase_uid', sa.String(length=128), nullable=True)
    )
    op.create_index(
        op.f('ix_users_firebase_uid'),
        'users',
        ['firebase_uid'],
        unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_users_firebase_uid'), table_name='users')
    op.drop_column('users', 'firebase_uid')
