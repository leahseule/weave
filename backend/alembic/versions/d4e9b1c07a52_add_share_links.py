"""add share_links

Revision ID: d4e9b1c07a52
Revises: c8a3f1029d47
Create Date: 2026-08-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e9b1c07a52'
down_revision: Union[str, None] = 'c8a3f1029d47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'share_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('project_id', sa.Integer(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_share_links_token'), 'share_links', ['token'], unique=True)
    op.create_index(op.f('ix_share_links_source_id'), 'share_links', ['source_id'])
    op.create_index(op.f('ix_share_links_project_id'), 'share_links', ['project_id'])
    op.create_index(op.f('ix_share_links_created_by'), 'share_links', ['created_by'])


def downgrade() -> None:
    op.drop_index(op.f('ix_share_links_created_by'), table_name='share_links')
    op.drop_index(op.f('ix_share_links_project_id'), table_name='share_links')
    op.drop_index(op.f('ix_share_links_source_id'), table_name='share_links')
    op.drop_index(op.f('ix_share_links_token'), table_name='share_links')
    op.drop_table('share_links')
