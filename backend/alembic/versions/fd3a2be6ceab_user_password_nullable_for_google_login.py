"""user password nullable for google login

Revision ID: fd3a2be6ceab
Revises: 38f05f0fd998
Create Date: 2026-07-22 05:29:33.624869

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fd3a2be6ceab'
down_revision: Union[str, None] = '38f05f0fd998'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column("users", "password_hash", existing_type=sa.Text(), nullable=False)
