"""Link row-end openings to their cross-route without inventing passage tiers."""
from alembic import op
import sqlalchemy as sa

revision = '074ca9e2b613'
down_revision = 'f16b72c8d431'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('routing_vertical_transitions', sa.Column('cross_route_uid', sa.Text(), nullable=True))
    op.create_foreign_key('fk_routing_opening_cross_route', 'routing_vertical_transitions', 'routing_cross_routes', ['cross_route_uid'], ['uid'], ondelete='CASCADE')
    op.create_index('ix_routing_vertical_transitions_cross_route_uid', 'routing_vertical_transitions', ['cross_route_uid'])


def downgrade():
    op.drop_index('ix_routing_vertical_transitions_cross_route_uid', table_name='routing_vertical_transitions')
    op.drop_constraint('fk_routing_opening_cross_route', 'routing_vertical_transitions', type_='foreignkey')
    op.drop_column('routing_vertical_transitions', 'cross_route_uid')
