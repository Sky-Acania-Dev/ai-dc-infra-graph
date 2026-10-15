"""Manual routing span markings, independent of generated graph identity."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '92e4c7b1a605'
down_revision = '0b81a6c2d901'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('routing_segment_annotations',
        sa.Column('uid', sa.Text(), primary_key=True),
        sa.Column('routing_layout_uid', sa.Text(), sa.ForeignKey('routing_layouts.uid', ondelete='CASCADE'), nullable=False),
        sa.Column('passage_band_uid', sa.Text(), sa.ForeignKey('routing_bands.uid', ondelete='CASCADE')),
        sa.Column('cross_route_uid', sa.Text(), sa.ForeignKey('routing_cross_routes.uid', ondelete='CASCADE')),
        sa.Column('start_station_in', sa.Integer()), sa.Column('end_station_in', sa.Integer()),
        sa.Column('from_passage_band_uid', sa.Text(), sa.ForeignKey('routing_bands.uid', ondelete='CASCADE')),
        sa.Column('to_passage_band_uid', sa.Text(), sa.ForeignKey('routing_bands.uid', ondelete='CASCADE')),
        sa.Column('tier', sa.Integer()),
        sa.Column('usable', sa.Boolean(), nullable=False),
        sa.Column('cable_classes', postgresql.JSONB(), nullable=False),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint('tier IS NULL OR tier BETWEEN 1 AND 3', name='ck_routing_annotation_tier'),
        sa.CheckConstraint("(passage_band_uid IS NOT NULL AND cross_route_uid IS NULL AND start_station_in IS NOT NULL AND end_station_in IS NOT NULL AND end_station_in > start_station_in AND start_station_in >= 0 AND from_passage_band_uid IS NULL AND to_passage_band_uid IS NULL) OR (passage_band_uid IS NULL AND cross_route_uid IS NOT NULL AND start_station_in IS NULL AND end_station_in IS NULL AND from_passage_band_uid IS NOT NULL AND to_passage_band_uid IS NOT NULL AND from_passage_band_uid <> to_passage_band_uid)", name='ck_routing_annotation_span'),
    )
    for field in ('routing_layout_uid', 'passage_band_uid', 'cross_route_uid'):
        op.create_index(f'ix_routing_segment_annotations_{field}', 'routing_segment_annotations', [field])


def downgrade() -> None:
    op.drop_table('routing_segment_annotations')
