"""per-user drive and settings

Revision ID: 38f05f0fd998
Revises: e81b7241f8af
Create Date: 2026-07-22 05:23:46.200741

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '38f05f0fd998'
down_revision: Union[str, None] = 'e81b7241f8af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # settings: 전역(key PK) → 사용자별((user_id, key) PK). 값은 재입력 가능하므로 재생성.
    op.drop_table("settings")
    op.create_table(
        "settings",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "key"),
    )
    # drive_connections: 사용자별. 기존 전역 토큰은 삭제(재연결 필요).
    op.execute("DELETE FROM drive_connections")
    op.add_column(
        "drive_connections", sa.Column("user_id", sa.Integer(), nullable=False)
    )
    op.create_foreign_key(
        "fk_drive_connections_user_id",
        "drive_connections",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_drive_connections_user_id",
        "drive_connections",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_drive_connections_user_id", table_name="drive_connections")
    op.drop_constraint(
        "fk_drive_connections_user_id", "drive_connections", type_="foreignkey"
    )
    op.drop_column("drive_connections", "user_id")
    op.drop_table("settings")
    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )
