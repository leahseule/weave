"""add NOTE source type

Revision ID: 2f20de75eb2f
Revises: 6c6edff4d2b5
Create Date: 2026-07-21 05:49:38.551924

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2f20de75eb2f'
down_revision: Union[str, None] = '6c6edff4d2b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres enum에 값 추가 (PG12+는 트랜잭션 내 ADD VALUE 허용)
    op.execute("ALTER TYPE source_type ADD VALUE IF NOT EXISTS 'NOTE'")


def downgrade() -> None:
    # enum 값 제거는 Postgres에서 간단히 불가 — no-op
    pass
