"""Explicit manual group routes, stored as domain pathway intervals.

Revision ID: f16b72c8d431
Revises: e95f41c7a320
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'f16b72c8d431'
down_revision = 'e95f41c7a320'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('routing_manual_cable_routes',
        sa.Column('uid', sa.Text(), primary_key=True),
        sa.Column('routing_layout_uid', sa.Text(), sa.ForeignKey('routing_layouts.uid', ondelete='CASCADE'), nullable=False),
        sa.Column('source_cabinet_uid', sa.Text(), nullable=False),
        sa.Column('destination_cabinet_uid', sa.Text(), nullable=False),
        sa.Column('start_tier', sa.Integer(), nullable=False),
        sa.Column('end_tier', sa.Integer(), nullable=False),
        sa.Column('cable_type', sa.Text(), nullable=False),
        sa.Column('legs', JSONB(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('version', sa.Text(), nullable=False),
        sa.Column('updated_by', sa.Text(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('routing_layout_uid', 'source_cabinet_uid', 'destination_cabinet_uid', 'cable_type', name='uq_routing_manual_group'),
        sa.CheckConstraint('source_cabinet_uid != destination_cabinet_uid AND revision > 0 AND start_tier BETWEEN 1 AND 3 AND end_tier BETWEEN 1 AND 3', name='ck_routing_manual_group'))
    for column in ('routing_layout_uid', 'source_cabinet_uid', 'destination_cabinet_uid'):
        op.create_index(f'ix_routing_manual_cable_routes_{column}', 'routing_manual_cable_routes', [column])


def downgrade():
    op.drop_table('routing_manual_cable_routes')
