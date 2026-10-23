"""Logical whole-section containers for actual cable unit ordering."""
from alembic import op
import sqlalchemy as sa

revision = '3a7c0d9e5f21'
down_revision = '2b6e9a1c4d70'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('routing_bundle_placements', sa.Column('is_section_container', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.drop_constraint('ck_routing_bundle_occupation','routing_bundle_placements',type_='check')
    op.create_check_constraint('ck_routing_bundle_occupation','routing_bundle_placements',"(is_section_container AND layer IS NULL AND offset_across_in IS NULL AND source_kind = 'MANUAL') OR (NOT is_section_container AND (layer IS NOT NULL OR offset_across_in IS NOT NULL))")


def downgrade():
    # Only whole-section ordering containers belong to this migration. Existing
    # physical placements and every manual cable route are preserved.
    op.execute(sa.text('DELETE FROM routing_bundle_placements WHERE is_section_container'))
    op.drop_constraint('ck_routing_bundle_occupation','routing_bundle_placements',type_='check')
    op.create_check_constraint('ck_routing_bundle_occupation','routing_bundle_placements','layer IS NOT NULL OR offset_across_in IS NOT NULL')
    op.drop_column('routing_bundle_placements', 'is_section_container')
