"""Multi-cell and rectangular occupations, bundle connections and cabinet attachments."""
from alembic import op
import sqlalchemy as sa

revision = 'c73a91de4826'
down_revision = 'b5f63c9e0214'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('routing_segment_annotations', sa.Column('grid_columns', sa.Integer(), nullable=False, server_default='12'))
    op.add_column('routing_segment_annotations', sa.Column('grid_rows', sa.Integer(), nullable=False, server_default='8'))
    op.add_column('routing_segment_annotations', sa.Column('section_height_in', sa.Integer()))
    # Preserve any previously configured ordinal positions outside the new default grid.
    op.execute('UPDATE routing_segment_annotations a SET grid_columns = GREATEST(12, COALESCE((SELECT MAX(position) FROM routing_bundle_placements p WHERE p.segment_annotation_uid = a.uid), 0)), grid_rows = GREATEST(8, COALESCE((SELECT MAX(layer) FROM routing_bundle_placements p WHERE p.segment_annotation_uid = a.uid), 0))')
    op.create_check_constraint('ck_routing_section_grid', 'routing_segment_annotations', 'grid_columns BETWEEN 1 AND 64 AND grid_rows BETWEEN 1 AND 64')
    op.create_check_constraint('ck_routing_section_height', 'routing_segment_annotations', 'section_height_in IS NULL OR section_height_in > 0')
    op.alter_column('routing_bundle_placements', 'layer', nullable=True)
    op.alter_column('routing_bundle_placements', 'position', nullable=True)
    for field in ('slot_width', 'slot_height'):
        op.add_column('routing_bundle_placements', sa.Column(field, sa.Integer(), server_default='1'))
    for field in ('offset_across_in', 'offset_up_in', 'occupied_width_in', 'occupied_height_in'):
        op.add_column('routing_bundle_placements', sa.Column(field, sa.Integer()))
    op.drop_constraint('ck_routing_bundle_position', 'routing_bundle_placements', type_='check')
    op.create_check_constraint('ck_routing_bundle_position', 'routing_bundle_placements', 'tier BETWEEN 1 AND 3')
    op.create_check_constraint('ck_routing_bundle_slots', 'routing_bundle_placements', '(layer IS NULL AND position IS NULL AND slot_width IS NULL AND slot_height IS NULL) OR (layer IS NOT NULL AND position IS NOT NULL AND slot_width IS NOT NULL AND slot_height IS NOT NULL AND layer BETWEEN 1 AND 64 AND position BETWEEN 1 AND 64 AND slot_width BETWEEN 1 AND 64 AND slot_height BETWEEN 1 AND 64)')
    op.create_check_constraint('ck_routing_bundle_rectangle', 'routing_bundle_placements', '(offset_across_in IS NULL AND offset_up_in IS NULL AND occupied_width_in IS NULL AND occupied_height_in IS NULL) OR (offset_across_in IS NOT NULL AND offset_up_in IS NOT NULL AND occupied_width_in IS NOT NULL AND occupied_height_in IS NOT NULL AND offset_across_in >= 0 AND offset_up_in >= 0 AND occupied_width_in > 0 AND occupied_height_in > 0)')
    op.create_check_constraint('ck_routing_bundle_occupation', 'routing_bundle_placements', 'layer IS NOT NULL OR offset_across_in IS NOT NULL')
    common = lambda: [sa.Column('uid', sa.Text(), primary_key=True),
        sa.Column('routing_layout_uid', sa.Text(), sa.ForeignKey('routing_layouts.uid', ondelete='CASCADE'), nullable=False),
        sa.Column('notes', sa.Text()), sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]
    op.create_table('routing_bundle_connections', *common(),
        sa.Column('from_placement_uid', sa.Text(), sa.ForeignKey('routing_bundle_placements.uid', ondelete='CASCADE'), nullable=False),
        sa.Column('from_end', sa.Text(), nullable=False),
        sa.Column('to_placement_uid', sa.Text(), sa.ForeignKey('routing_bundle_placements.uid', ondelete='CASCADE'), nullable=False),
        sa.Column('to_end', sa.Text(), nullable=False),
        sa.Column('vertical_transition_uid', sa.Text(), sa.ForeignKey('routing_vertical_transitions.uid')),
        sa.CheckConstraint("from_end IN ('START','END') AND to_end IN ('START','END') AND from_placement_uid <> to_placement_uid", name='ck_routing_connection_ends'))
    op.create_table('routing_cabinet_attachments', *common(),
        sa.Column('segment_annotation_uid', sa.Text(), sa.ForeignKey('routing_segment_annotations.uid', ondelete='CASCADE'), nullable=False),
        sa.Column('cabinet_uid', sa.Text(), nullable=False), sa.Column('offset_in', sa.Integer(), nullable=False),
        sa.Column('tier', sa.Integer()), sa.Column('label', sa.Text()),
        sa.CheckConstraint('offset_in >= 0 AND (tier IS NULL OR tier BETWEEN 1 AND 3)', name='ck_routing_attachment_position'))
    for table, fields in (('routing_bundle_connections', ('routing_layout_uid', 'from_placement_uid', 'to_placement_uid', 'vertical_transition_uid')),
                          ('routing_cabinet_attachments', ('routing_layout_uid', 'segment_annotation_uid', 'cabinet_uid'))):
        for field in fields:
            op.create_index(f'ix_{table}_{field}', table, [field])


def downgrade():
    # The old schema cannot represent rectangle-only placements or multi-cell footprints.
    # Refuse a lossy rollback until those records have been explicitly converted/removed.
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM routing_bundle_placements WHERE layer IS NULL OR slot_width <> 1 OR slot_height <> 1 OR offset_across_in IS NOT NULL) THEN RAISE EXCEPTION 'Convert rectangular and multi-cell occupations before downgrading'; END IF; END $$")
    op.drop_table('routing_cabinet_attachments')
    op.drop_table('routing_bundle_connections')
    for constraint in ('ck_routing_bundle_slots', 'ck_routing_bundle_rectangle', 'ck_routing_bundle_occupation'):
        op.drop_constraint(constraint, 'routing_bundle_placements', type_='check')
    for field in ('slot_width', 'slot_height', 'offset_across_in', 'offset_up_in', 'occupied_width_in', 'occupied_height_in'):
        op.drop_column('routing_bundle_placements', field)
    op.alter_column('routing_bundle_placements', 'layer', nullable=False)
    op.alter_column('routing_bundle_placements', 'position', nullable=False)
    op.drop_constraint('ck_routing_bundle_position', 'routing_bundle_placements', type_='check')
    op.create_check_constraint('ck_routing_bundle_position', 'routing_bundle_placements', 'tier BETWEEN 1 AND 3 AND layer BETWEEN 1 AND 64 AND position BETWEEN 1 AND 64')
    for constraint in ('ck_routing_section_grid', 'ck_routing_section_height'):
        op.drop_constraint(constraint, 'routing_segment_annotations', type_='check')
    for field in ('grid_columns', 'grid_rows', 'section_height_in'):
        op.drop_column('routing_segment_annotations', field)
