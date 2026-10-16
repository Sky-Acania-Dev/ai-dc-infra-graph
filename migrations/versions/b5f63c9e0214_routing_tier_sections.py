"""Route-tier elevations above finished floor and ordinal bundle sections."""
from alembic import op
import sqlalchemy as sa

revision = 'b5f63c9e0214'
down_revision = '92e4c7b1a605'
branch_labels = None
depends_on = None


def upgrade():
    for table, name in (('routing_cross_route_tiers', 'cross'), ('routing_passage_tiers', 'passage')):
        op.add_column(table, sa.Column('elevation_in', sa.Integer(), nullable=True))
        op.create_check_constraint(f'ck_routing_{name}_elevation', table, 'elevation_in IS NULL OR elevation_in >= 0')
    op.add_column('routing_segment_annotations', sa.Column('section_reference', sa.Text(), nullable=True))
    op.create_table('routing_bundle_placements',
        sa.Column('uid', sa.Text(), primary_key=True),
        sa.Column('routing_layout_uid', sa.Text(), sa.ForeignKey('routing_layouts.uid', ondelete='CASCADE'), nullable=False),
        sa.Column('segment_annotation_uid', sa.Text(), sa.ForeignKey('routing_segment_annotations.uid', ondelete='CASCADE'), nullable=False),
        sa.Column('tier', sa.Integer(), nullable=False), sa.Column('layer', sa.Integer(), nullable=False), sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('source_kind', sa.Text(), nullable=False), sa.Column('source_uid', sa.Text()), sa.Column('label', sa.Text()),
        sa.Column('cable_class', sa.Text()), sa.Column('notes', sa.Text()), sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('segment_annotation_uid', 'tier', 'layer', 'position', name='uq_routing_bundle_position'),
        sa.CheckConstraint('tier BETWEEN 1 AND 3 AND layer BETWEEN 1 AND 64 AND position BETWEEN 1 AND 64', name='ck_routing_bundle_position'),
        sa.CheckConstraint("(source_kind = 'MANUAL' AND source_uid IS NULL AND label IS NOT NULL AND length(label) > 0) OR (source_kind IN ('BUNDLE','GROUP') AND source_uid IS NOT NULL)", name='ck_routing_bundle_source'),
    )
    for field in ('routing_layout_uid', 'segment_annotation_uid'):
        op.create_index(f'ix_routing_bundle_placements_{field}', 'routing_bundle_placements', [field])


def downgrade():
    op.drop_table('routing_bundle_placements')
    op.drop_column('routing_segment_annotations', 'section_reference')
    for table, name in (('routing_cross_route_tiers', 'cross'), ('routing_passage_tiers', 'passage')):
        op.drop_constraint(f'ck_routing_{name}_elevation', table, type_='check')
        op.drop_column(table, 'elevation_in')
