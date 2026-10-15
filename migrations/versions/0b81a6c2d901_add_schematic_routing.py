"""Add technician schematic routing domain (no generated graph tables)."""
from alembic import op
import sqlalchemy as sa

revision = '0b81a6c2d901'
down_revision = '4d8f1b2c9a73'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('routing_layouts',
        sa.Column('room_uid', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('physical_hall_code', sa.Text(), nullable=False),
        sa.Column('cabinet_row_depth_in', sa.Integer(), nullable=False),
        sa.Column('hot_aisle_clear_in', sa.Integer(), nullable=False),
        sa.Column('cold_aisle_clear_in', sa.Integer(), nullable=False),
        sa.Column('row_pair_module_in', sa.Integer(), nullable=False),
        sa.Column('section_extra_gap_in', sa.Integer(), nullable=False),
        sa.Column('default_cross_route_width_in', sa.Integer(), nullable=False),
        sa.Column('max_tier', sa.Integer(), nullable=False),
        sa.Column('cabinets_per_row', sa.Integer(), nullable=False),
        sa.Column('uid', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('hot_aisle_clear_in > 0 AND cold_aisle_clear_in > 0', name='ck_routing_aisles'),
        sa.CheckConstraint('cabinets_per_row > 0', name='ck_routing_cabinet_count'),
        sa.CheckConstraint('default_cross_route_width_in > 0 AND default_cross_route_width_in % 2 = 0', name='ck_routing_default_width'),
        sa.CheckConstraint('section_extra_gap_in > 0 AND section_extra_gap_in % 2 = 0', name='ck_routing_gap'),
        sa.CheckConstraint('max_tier = 3', name='ck_routing_max_tier'),
        sa.CheckConstraint('row_pair_module_in = 2 * cabinet_row_depth_in + hot_aisle_clear_in + cold_aisle_clear_in', name='ck_routing_module'),
        sa.CheckConstraint('cabinet_row_depth_in > 0 AND cabinet_row_depth_in % 2 = 0', name='ck_routing_row_depth'),
        sa.ForeignKeyConstraint(['room_uid'], ['rooms.uid']),
        sa.PrimaryKeyConstraint('uid'),
        sa.UniqueConstraint('room_uid', name=None),
    )
    op.create_table('routing_bands',
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('kind', sa.Text(), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('width_in', sa.Integer(), nullable=False),
        sa.Column('routing_layout_uid', sa.Text(), nullable=False),
        sa.Column('uid', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("(kind = 'PASSAGE' AND code IN ('NORTH','CENTRAL','SOUTH')) OR (kind = 'ROW_FIELD' AND code IN ('NORTH_FIELD','SOUTH_FIELD'))", name='ck_routing_band_kind'),
        sa.CheckConstraint('ordinal >= 0', name='ck_routing_band_ordinal'),
        sa.CheckConstraint('width_in > 0 AND width_in % 2 = 0', name='ck_routing_band_width'),
        sa.ForeignKeyConstraint(['routing_layout_uid'], ['routing_layouts.uid'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('uid'),
        sa.UniqueConstraint('routing_layout_uid', 'code', name='uq_routing_band_code'),
        sa.UniqueConstraint('routing_layout_uid', 'ordinal', name='uq_routing_band_ordinal'),
    )
    op.create_index('ix_routing_bands_routing_layout_uid', 'routing_bands', ['routing_layout_uid'])
    op.create_table('routing_sections',
        sa.Column('ordinal', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('room_uid', sa.Text(), nullable=True),
        sa.Column('routing_layout_uid', sa.Text(), nullable=False),
        sa.Column('uid', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('ordinal BETWEEN 1 AND 5', name='ck_routing_section_ordinal'),
        sa.ForeignKeyConstraint(['routing_layout_uid'], ['routing_layouts.uid'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['room_uid'], ['rooms.uid']),
        sa.PrimaryKeyConstraint('uid'),
        sa.UniqueConstraint('routing_layout_uid', 'ordinal', name='uq_routing_section_ordinal'),
    )
    op.create_index('ix_routing_sections_routing_layout_uid', 'routing_sections', ['routing_layout_uid'])
    op.create_table('routing_passage_tiers',
        sa.Column('passage_band_uid', sa.Text(), nullable=False),
        sa.Column('tier', sa.Integer(), nullable=False),
        sa.Column('pathway_type', sa.Text(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('routing_layout_uid', sa.Text(), nullable=False),
        sa.Column('uid', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('tier BETWEEN 1 AND 3', name='ck_routing_passage_tier'),
        sa.CheckConstraint("pathway_type IN ('LADDER_RACK','BASKET_TRAY')", name='ck_routing_passage_type'),
        sa.ForeignKeyConstraint(['passage_band_uid'], ['routing_bands.uid'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['routing_layout_uid'], ['routing_layouts.uid'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('uid'),
        sa.UniqueConstraint('passage_band_uid', 'tier', name='uq_routing_passage_tier'),
    )
    op.create_index('ix_routing_passage_tiers_passage_band_uid', 'routing_passage_tiers', ['passage_band_uid'])
    op.create_index('ix_routing_passage_tiers_routing_layout_uid', 'routing_passage_tiers', ['routing_layout_uid'])
    op.create_table('routing_row_pairs',
        sa.Column('routing_section_uid', sa.Text(), nullable=False),
        sa.Column('row_field_band_uid', sa.Text(), nullable=False),
        sa.Column('ordinal_in_section', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=True),
        sa.Column('routing_layout_uid', sa.Text(), nullable=False),
        sa.Column('uid', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('ordinal_in_section >= 1', name='ck_routing_pair_ordinal'),
        sa.ForeignKeyConstraint(['row_field_band_uid'], ['routing_bands.uid']),
        sa.ForeignKeyConstraint(['routing_section_uid'], ['routing_sections.uid'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['routing_layout_uid'], ['routing_layouts.uid'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('uid'),
        sa.UniqueConstraint('routing_section_uid', 'row_field_band_uid', 'ordinal_in_section', name='uq_routing_pair_ordinal'),
    )
    op.create_index('ix_routing_row_pairs_routing_layout_uid', 'routing_row_pairs', ['routing_layout_uid'])
    op.create_index('ix_routing_row_pairs_routing_section_uid', 'routing_row_pairs', ['routing_section_uid'])
    op.create_index('ix_routing_row_pairs_row_field_band_uid', 'routing_row_pairs', ['row_field_band_uid'])
    op.create_table('routing_vertical_transitions',
        sa.Column('passage_band_uid', sa.Text(), nullable=False),
        sa.Column('station_in', sa.Integer(), nullable=False),
        sa.Column('lower_tier', sa.Integer(), nullable=False),
        sa.Column('upper_tier', sa.Integer(), nullable=False),
        sa.Column('label', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('routing_layout_uid', sa.Text(), nullable=False),
        sa.Column('uid', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('lower_tier >= 1 AND upper_tier <= 3 AND upper_tier = lower_tier + 1', name='ck_routing_vertical_adjacent'),
        sa.CheckConstraint('station_in >= 0', name='ck_routing_vertical_station'),
        sa.ForeignKeyConstraint(['passage_band_uid'], ['routing_bands.uid'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['routing_layout_uid'], ['routing_layouts.uid'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('uid'),
    )
    op.create_index('ix_routing_vertical_transitions_passage_band_uid', 'routing_vertical_transitions', ['passage_band_uid'])
    op.create_index('ix_routing_vertical_transitions_routing_layout_uid', 'routing_vertical_transitions', ['routing_layout_uid'])
    op.create_table('routing_cabinet_rows',
        sa.Column('row_pair_uid', sa.Text(), nullable=False),
        sa.Column('position_in_pair', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('existing_row_reference', sa.Text(), nullable=True),
        sa.Column('cabinet_number_start', sa.Integer(), nullable=True),
        sa.Column('cabinet_number_end', sa.Integer(), nullable=True),
        sa.Column('cold_route_face_offset_in', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('routing_layout_uid', sa.Text(), nullable=False),
        sa.Column('uid', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('(cabinet_number_start IS NULL AND cabinet_number_end IS NULL) OR (cabinet_number_start IS NOT NULL AND cabinet_number_end IS NOT NULL AND cabinet_number_start > 0 AND cabinet_number_end >= cabinet_number_start)', name='ck_routing_row_cabinets'),
        sa.CheckConstraint('cold_route_face_offset_in >= 0', name='ck_routing_row_offset'),
        sa.CheckConstraint("position_in_pair IN ('A','B')", name='ck_routing_row_position'),
        sa.ForeignKeyConstraint(['routing_layout_uid'], ['routing_layouts.uid'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['row_pair_uid'], ['routing_row_pairs.uid'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('uid'),
        sa.UniqueConstraint('row_pair_uid', 'position_in_pair', name='uq_routing_row_position'),
    )
    op.create_index('ix_routing_cabinet_rows_routing_layout_uid', 'routing_cabinet_rows', ['routing_layout_uid'])
    op.create_index('ix_routing_cabinet_rows_row_pair_uid', 'routing_cabinet_rows', ['row_pair_uid'])
    op.create_table('routing_cross_routes',
        sa.Column('kind', sa.Text(), nullable=False),
        sa.Column('cabinet_row_uid', sa.Text(), nullable=True),
        sa.Column('section_boundary_after_section_uid', sa.Text(), nullable=True),
        sa.Column('width_in', sa.Integer(), nullable=False),
        sa.Column('station_source', sa.Text(), nullable=False),
        sa.Column('manual_station_in', sa.Integer(), nullable=True),
        sa.Column('label', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('routing_layout_uid', sa.Text(), nullable=False),
        sa.Column('uid', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("(kind = 'CABINET_COLD_AISLE' AND cabinet_row_uid IS NOT NULL AND section_boundary_after_section_uid IS NULL) OR (kind = 'SECTION_GAP' AND cabinet_row_uid IS NULL AND section_boundary_after_section_uid IS NOT NULL)", name='ck_routing_cross_association'),
        sa.CheckConstraint("(station_source = 'DERIVED' AND manual_station_in IS NULL) OR (station_source IN ('MANUAL','FIELD_MEASURED') AND manual_station_in IS NOT NULL AND manual_station_in >= 0)", name='ck_routing_cross_station'),
        sa.CheckConstraint('width_in > 0 AND width_in % 2 = 0', name='ck_routing_cross_width'),
        sa.ForeignKeyConstraint(['routing_layout_uid'], ['routing_layouts.uid'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cabinet_row_uid'], ['routing_cabinet_rows.uid'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['section_boundary_after_section_uid'], ['routing_sections.uid'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('uid'),
        sa.UniqueConstraint('section_boundary_after_section_uid', name='uq_routing_cross_boundary'),
        sa.UniqueConstraint('cabinet_row_uid', name='uq_routing_cross_cabinet'),
    )
    op.create_index('ix_routing_cross_routes_routing_layout_uid', 'routing_cross_routes', ['routing_layout_uid'])
    op.create_table('routing_cross_route_tiers',
        sa.Column('cross_route_uid', sa.Text(), nullable=False),
        sa.Column('tier', sa.Integer(), nullable=False),
        sa.Column('pathway_type', sa.Text(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('routing_layout_uid', sa.Text(), nullable=False),
        sa.Column('uid', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('tier BETWEEN 1 AND 3', name='ck_routing_cross_tier'),
        sa.CheckConstraint("pathway_type IN ('LADDER_RACK','BASKET_TRAY')", name='ck_routing_cross_type'),
        sa.ForeignKeyConstraint(['routing_layout_uid'], ['routing_layouts.uid'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cross_route_uid'], ['routing_cross_routes.uid'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('uid'),
        sa.UniqueConstraint('cross_route_uid', 'tier', name='uq_routing_cross_tier'),
    )
    op.create_index('ix_routing_cross_route_tiers_cross_route_uid', 'routing_cross_route_tiers', ['cross_route_uid'])
    op.create_index('ix_routing_cross_route_tiers_routing_layout_uid', 'routing_cross_route_tiers', ['routing_layout_uid'])


def downgrade() -> None:
    op.drop_index('ix_routing_cross_route_tiers_cross_route_uid', table_name='routing_cross_route_tiers')
    op.drop_index('ix_routing_cross_route_tiers_routing_layout_uid', table_name='routing_cross_route_tiers')
    op.drop_table('routing_cross_route_tiers')
    op.drop_index('ix_routing_cross_routes_routing_layout_uid', table_name='routing_cross_routes')
    op.drop_table('routing_cross_routes')
    op.drop_index('ix_routing_cabinet_rows_routing_layout_uid', table_name='routing_cabinet_rows')
    op.drop_index('ix_routing_cabinet_rows_row_pair_uid', table_name='routing_cabinet_rows')
    op.drop_table('routing_cabinet_rows')
    op.drop_index('ix_routing_vertical_transitions_passage_band_uid', table_name='routing_vertical_transitions')
    op.drop_index('ix_routing_vertical_transitions_routing_layout_uid', table_name='routing_vertical_transitions')
    op.drop_table('routing_vertical_transitions')
    op.drop_index('ix_routing_row_pairs_routing_layout_uid', table_name='routing_row_pairs')
    op.drop_index('ix_routing_row_pairs_routing_section_uid', table_name='routing_row_pairs')
    op.drop_index('ix_routing_row_pairs_row_field_band_uid', table_name='routing_row_pairs')
    op.drop_table('routing_row_pairs')
    op.drop_index('ix_routing_passage_tiers_passage_band_uid', table_name='routing_passage_tiers')
    op.drop_index('ix_routing_passage_tiers_routing_layout_uid', table_name='routing_passage_tiers')
    op.drop_table('routing_passage_tiers')
    op.drop_index('ix_routing_sections_routing_layout_uid', table_name='routing_sections')
    op.drop_table('routing_sections')
    op.drop_index('ix_routing_bands_routing_layout_uid', table_name='routing_bands')
    op.drop_table('routing_bands')
    op.drop_table('routing_layouts')
