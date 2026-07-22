"""project members rbac

Revision ID: 6aa552c2223e
Revises: fd3a2be6ceab
Create Date: 2026-07-22 05:40:54.525766

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6aa552c2223e'
down_revision: Union[str, None] = 'fd3a2be6ceab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "project_members",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "role",
            sa.Enum("OWNER", "EDITOR", "VIEWER", name="project_role"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("project_id", "user_id"),
    )
    op.create_index(
        "ix_project_members_user_id", "project_members", ["user_id"]
    )
    # 기존 프로젝트의 owner_id를 OWNER 멤버로 백필
    op.execute(
        "INSERT INTO project_members (project_id, user_id, role, created_at) "
        "SELECT id, owner_id, 'OWNER', now() FROM projects "
        "WHERE owner_id IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_project_members_user_id", table_name="project_members")
    op.drop_table("project_members")
    sa.Enum(name="project_role").drop(op.get_bind(), checkfirst=True)
