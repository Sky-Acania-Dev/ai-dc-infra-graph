"""Junction working areas, cable turn starts and local crossing order."""
from alembic import op
import sqlalchemy as sa

revision = '187a4f03c852'
down_revision = '074ca9e2b613'
branch_labels = None
depends_on = None


def upgrade():
    def common():
        return [sa.Column('uid',sa.Text(),primary_key=True),sa.Column('routing_layout_uid',sa.Text(),sa.ForeignKey('routing_layouts.uid',ondelete='CASCADE'),nullable=False),
                sa.Column('created_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),
                sa.Column('notes',sa.Text()),sa.Column('enabled',sa.Boolean(),nullable=False)]
    op.create_table('routing_junction_areas',*common(),
        sa.Column('passage_band_uid',sa.Text(),sa.ForeignKey('routing_bands.uid',ondelete='CASCADE'),nullable=False),
        sa.Column('cross_route_uid',sa.Text(),sa.ForeignKey('routing_cross_routes.uid',ondelete='CASCADE')),
        sa.Column('station_in',sa.Integer()),sa.Column('tier',sa.Integer(),nullable=False),
        *[sa.Column(name,sa.Integer(),nullable=False) for name in ('west_extension_in','east_extension_in','north_extension_in','south_extension_in')],
        sa.Column('usable_height_in',sa.Integer()),sa.Column('provenance',sa.Text(),nullable=False),sa.Column('label',sa.Text()),
        sa.UniqueConstraint('passage_band_uid','cross_route_uid','tier',name='uq_routing_junction_cross_anchor'),
        sa.UniqueConstraint('passage_band_uid','station_in','tier',name='uq_routing_junction_station_anchor'),
        sa.CheckConstraint('tier BETWEEN 1 AND 3',name='ck_routing_junction_tier'),
        sa.CheckConstraint('(cross_route_uid IS NOT NULL AND station_in IS NULL) OR (cross_route_uid IS NULL AND station_in IS NOT NULL AND station_in >= 0)',name='ck_routing_junction_anchor'),
        sa.CheckConstraint('west_extension_in >= 0 AND east_extension_in >= 0 AND north_extension_in >= 0 AND south_extension_in >= 0 AND (usable_height_in IS NULL OR usable_height_in > 0)',name='ck_routing_junction_dimensions'),
        sa.CheckConstraint("provenance IN ('SCHEMATIC','MANUAL','FIELD_MEASURED')",name='ck_routing_junction_provenance'))
    for field in ('routing_layout_uid','passage_band_uid','cross_route_uid'):
        op.create_index(f'ix_routing_junction_areas_{field}','routing_junction_areas',[field])
    for name, kind in (('junction_area_uid', sa.Text()), ('from_turn_start_in', sa.Integer()), ('to_turn_start_in', sa.Integer())):
        op.add_column('routing_bundle_connections', sa.Column(name, kind, nullable=True))
    op.create_foreign_key('fk_routing_connection_junction', 'routing_bundle_connections', 'routing_junction_areas', ['junction_area_uid'], ['uid'], ondelete='SET NULL')
    op.create_index('ix_routing_bundle_connections_junction_area_uid', 'routing_bundle_connections', ['junction_area_uid'])
    op.create_check_constraint('ck_routing_connection_turn_starts', 'routing_bundle_connections', '(from_turn_start_in IS NULL AND to_turn_start_in IS NULL) OR (from_turn_start_in IS NOT NULL AND to_turn_start_in IS NOT NULL AND from_turn_start_in >= 0 AND to_turn_start_in >= 0)')
    op.create_table('routing_junction_crossings',*common(),
        sa.Column('above_connection_uid',sa.Text(),sa.ForeignKey('routing_bundle_connections.uid',ondelete='CASCADE'),nullable=False),
        sa.Column('below_connection_uid',sa.Text(),sa.ForeignKey('routing_bundle_connections.uid',ondelete='CASCADE'),nullable=False),sa.Column('clearance_in',sa.Integer()),
        sa.UniqueConstraint('above_connection_uid','below_connection_uid',name='uq_routing_junction_crossing'),
        sa.CheckConstraint('above_connection_uid <> below_connection_uid AND (clearance_in IS NULL OR clearance_in >= 0)',name='ck_routing_junction_crossing'))
    for field in ('routing_layout_uid','above_connection_uid','below_connection_uid'):
        op.create_index(f'ix_routing_junction_crossings_{field}','routing_junction_crossings',[field])


def downgrade():
    op.drop_table('routing_junction_crossings')
    op.drop_constraint('ck_routing_connection_turn_starts', 'routing_bundle_connections', type_='check')
    op.drop_index('ix_routing_bundle_connections_junction_area_uid', table_name='routing_bundle_connections')
    op.drop_constraint('fk_routing_connection_junction', 'routing_bundle_connections', type_='foreignkey')
    for name in ('to_turn_start_in', 'from_turn_start_in', 'junction_area_uid'):
        op.drop_column('routing_bundle_connections', name)
    op.drop_table('routing_junction_areas')
