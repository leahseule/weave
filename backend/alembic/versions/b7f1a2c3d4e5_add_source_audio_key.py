"""add source audio_key

Revision ID: b7f1a2c3d4e5
Revises: 6aa552c2223e
Create Date: 2026-07-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7f1a2c3d4e5'
down_revision: Union[str, None] = '6aa552c2223e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sources', sa.Column('audio_key', sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column('sources', 'audio_key')
