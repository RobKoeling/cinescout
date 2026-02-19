"""add pricing to cinemas

Revision ID: fa43a344e13d
Revises: 634b659320ca
Create Date: 2026-02-19 20:17:43.286157+00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fa43a344e13d'
down_revision: Union[str, None] = '634b659320ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('cinemas', sa.Column('pricing', sa.dialects.postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('cinemas', 'pricing')
