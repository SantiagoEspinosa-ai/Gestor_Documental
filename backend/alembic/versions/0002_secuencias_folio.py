"""Tabla secuencias_folio: numeracion atomica de folios por (proceso, anio).

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea secuencias_folio."""
    op.create_table('secuencias_folio',
    sa.Column('proceso', sa.String(length=50), nullable=False),
    sa.Column('anio', sa.Integer(), nullable=False),
    sa.Column('ultimo', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['proceso'], ['procesos.nombre'], ),
    sa.PrimaryKeyConstraint('proceso', 'anio')
    )


def downgrade() -> None:
    """Borra secuencias_folio."""
    op.drop_table('secuencias_folio')
