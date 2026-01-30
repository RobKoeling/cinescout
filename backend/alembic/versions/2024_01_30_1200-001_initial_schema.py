"""initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-30 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create cinemas table
    op.create_table(
        'cinemas',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('address', sa.Text(), nullable=False),
        sa.Column('postcode', sa.String(length=20), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('website', sa.String(length=500), nullable=True),
        sa.Column('scraper_type', sa.String(length=50), nullable=False),
        sa.Column('scraper_config', JSONB(), nullable=True),
        sa.Column('has_online_booking', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('supports_availability_check', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_cinemas_city'), 'cinemas', ['city'], unique=False)

    # Create films table
    op.create_table(
        'films',
        sa.Column('id', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('tmdb_id', sa.Integer(), nullable=True),
        sa.Column('directors', ARRAY(sa.String()), nullable=True),
        sa.Column('countries', ARRAY(sa.String()), nullable=True),
        sa.Column('overview', sa.Text(), nullable=True),
        sa.Column('poster_path', sa.String(length=200), nullable=True),
        sa.Column('runtime', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_films_title'), 'films', ['title'], unique=False)
    op.create_index(op.f('ix_films_tmdb_id'), 'films', ['tmdb_id'], unique=True)

    # Create film_aliases table
    op.create_table(
        'film_aliases',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('normalized_title', sa.String(length=500), nullable=False),
        sa.Column('film_id', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['film_id'], ['films.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('normalized_title', name='uq_normalized_title')
    )
    op.create_index(op.f('ix_film_aliases_film_id'), 'film_aliases', ['film_id'], unique=False)
    op.create_index(op.f('ix_film_aliases_normalized_title'), 'film_aliases', ['normalized_title'], unique=False)

    # Create showings table
    op.create_table(
        'showings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('cinema_id', sa.String(length=100), nullable=False),
        sa.Column('film_id', sa.String(length=100), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('booking_url', sa.String(length=1000), nullable=True),
        sa.Column('screen_name', sa.String(length=100), nullable=True),
        sa.Column('format_tags', sa.String(length=200), nullable=True),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('raw_title', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['cinema_id'], ['cinemas.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['film_id'], ['films.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cinema_id', 'film_id', 'start_time', name='uq_cinema_film_time')
    )
    op.create_index(op.f('ix_showings_cinema_id'), 'showings', ['cinema_id'], unique=False)
    op.create_index(op.f('ix_showings_film_id'), 'showings', ['film_id'], unique=False)
    op.create_index(op.f('ix_showings_start_time'), 'showings', ['start_time'], unique=False)


def downgrade() -> None:
    op.drop_table('showings')
    op.drop_table('film_aliases')
    op.drop_table('films')
    op.drop_table('cinemas')
