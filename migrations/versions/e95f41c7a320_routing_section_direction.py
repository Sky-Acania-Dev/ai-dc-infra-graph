"""Cardinal section references and confirmed LBB01 longitudinal orientation.

Revision ID: e95f41c7a320
Revises: d84e30b6f219
"""
from alembic import op
import sqlalchemy as sa

revision = 'e95f41c7a320'
down_revision = 'd84e30b6f219'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('routing_layouts', sa.Column('longitudinal_direction', sa.Text(), nullable=True))
    op.create_check_constraint('ck_routing_longitudinal_direction', 'routing_layouts', "longitudinal_direction IS NULL OR longitudinal_direction IN ('EAST','WEST')")
    op.add_column('routing_segment_annotations', sa.Column('section_inner_direction', sa.Text(), nullable=True))
    op.create_check_constraint('ck_routing_section_direction', 'routing_segment_annotations', "section_inner_direction IS NULL OR section_inner_direction IN ('NORTH','SOUTH','EAST','WEST')")
    # User-confirmed cabinet-map top is West; Section 1 -> 5 runs East.
    op.execute("UPDATE routing_layouts SET longitudinal_direction = 'EAST' WHERE physical_hall_code = 'DH1' AND room_uid IN (SELECT uid FROM rooms WHERE project_uid = 'LBB01' AND building_uid = 'LBB01:A')")


def downgrade():
    op.drop_constraint('ck_routing_section_direction', 'routing_segment_annotations', type_='check')
    op.drop_column('routing_segment_annotations', 'section_inner_direction')
    op.drop_constraint('ck_routing_longitudinal_direction', 'routing_layouts', type_='check')
    op.drop_column('routing_layouts', 'longitudinal_direction')
