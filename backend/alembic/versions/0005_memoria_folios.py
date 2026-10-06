"""Tabla memoria_folios: resumen.md enmascarado de cada folio y su fragmento (H14, ADR-010 C4).

Igual que app.modulos.rag.modelos.MemoriaFolio (PERSONA_2). Sin vectores: la memoria guarda texto.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Crea memoria_folios."""
    op.create_table('memoria_folios',
    sa.Column('folio', sa.String(length=30), nullable=False),
    sa.Column('resumen_md', sa.Text(), nullable=False),
    sa.Column('fragmento', sa.Text(), nullable=False),
    sa.Column('actualizado_en', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['folio'], ['folios.folio'], ),
    sa.PrimaryKeyConstraint('folio')
    )


def downgrade() -> None:
    """Borra memoria_folios."""
    op.drop_table('memoria_folios')
