"""folios.creado_por: usuario que creo el folio con POST /folios (ADR-012, propuesto).

El integrador solo accede a sus folios; un folio anterior (NULL) no es de ningun integrador.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0007'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Anade folios.creado_por (NULL en los folios existentes)."""
    op.add_column('folios', sa.Column('creado_por', sa.String(length=100), nullable=True))


def downgrade() -> None:
    """Quita folios.creado_por."""
    # batch: SQLite antiguo no soporta DROP COLUMN (en PostgreSQL es un ALTER normal)
    with op.batch_alter_table('folios') as batch:
        batch.drop_column('creado_por')
