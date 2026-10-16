"""Scoped measured elevations with explicit top-tier references."""
from alembic import op
import sqlalchemy as sa

revision = 'd84e30b6f219'
down_revision = 'c73a91de4826'
branch_labels = None
depends_on = None


def upgrade():
    for field in ('bottom_basket_elevation_in', 'north_south_top_elevation_in'):
        op.add_column('routing_layouts', sa.Column(field, sa.Integer()))
    op.create_check_constraint('ck_routing_measured_elevations', 'routing_layouts', '(bottom_basket_elevation_in IS NULL OR bottom_basket_elevation_in >= 0) AND (north_south_top_elevation_in IS NULL OR north_south_top_elevation_in >= 0)')
    for table in ('routing_passage_tiers', 'routing_cross_route_tiers'):
        op.add_column(table, sa.Column('elevation_reference', sa.Text()))
        op.create_check_constraint(f'ck_{table}_elevation_reference', table, "elevation_reference IS NULL OR elevation_reference IN ('BOTTOM_BASKET','NORTH_SOUTH_TOP')")


def downgrade():
    # Preserve effective elevations when removing the reference mechanism.
    for table in ('routing_passage_tiers', 'routing_cross_route_tiers'):
        op.execute(f"UPDATE {table} t SET elevation_in = CASE t.elevation_reference WHEN 'BOTTOM_BASKET' THEN l.bottom_basket_elevation_in WHEN 'NORTH_SOUTH_TOP' THEN l.north_south_top_elevation_in ELSE t.elevation_in END FROM routing_layouts l WHERE t.routing_layout_uid = l.uid")
        op.drop_constraint(f'ck_{table}_elevation_reference', table, type_='check')
        op.drop_column(table, 'elevation_reference')
    op.drop_constraint('ck_routing_measured_elevations', 'routing_layouts', type_='check')
    for field in ('bottom_basket_elevation_in', 'north_south_top_elevation_in'):
        op.drop_column('routing_layouts', field)
