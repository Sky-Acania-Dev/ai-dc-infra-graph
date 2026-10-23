"""Bundle-local two-dimensional ordering of actual cable units."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '2b6e9a1c4d70'
down_revision = '187a4f03c852'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('routing_bundle_contents',
        sa.Column('uid', sa.Text(), primary_key=True),
        sa.Column('routing_layout_uid', sa.Text(), sa.ForeignKey('routing_layouts.uid', ondelete='CASCADE'), nullable=False),
        sa.Column('bundle_placement_uid', sa.Text(), sa.ForeignKey('routing_bundle_placements.uid', ondelete='CASCADE'), nullable=False),
        sa.Column('section_end', sa.Text(), nullable=False),
        sa.Column('grid_columns', sa.Integer(), nullable=False),
        sa.Column('grid_rows', sa.Integer(), nullable=False),
        sa.Column('units', postgresql.JSONB(), nullable=False),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('bundle_placement_uid', 'section_end', name='uq_routing_bundle_contents_end'),
        sa.CheckConstraint("section_end IN ('SPAN','START','END')", name='ck_routing_bundle_contents_end'),
        sa.CheckConstraint('grid_columns BETWEEN 1 AND 64 AND grid_rows BETWEEN 1 AND 64', name='ck_routing_bundle_contents_grid'))
    for name in ('routing_layout_uid', 'bundle_placement_uid'):
        op.create_index(f'ix_routing_bundle_contents_{name}', 'routing_bundle_contents', [name])


def downgrade():
    op.drop_table('routing_bundle_contents')
