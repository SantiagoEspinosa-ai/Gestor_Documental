"""documentos.retirado_en, retirado_por y motivo_retirada: retirar un documento sin borrarlo (ADR-013, propuesto).

Retirado = retirado_en no nulo. Los documentos existentes quedan sin retirar (NULL). El motivo se guarda tapado.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0008'
down_revision: Union[str, Sequence[str], None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Anade las tres columnas de la retirada (NULL en los documentos existentes)."""
    op.add_column('documentos', sa.Column('retirado_en', sa.DateTime(timezone=True), nullable=True))
    op.add_column('documentos', sa.Column('retirado_por', sa.String(length=100), nullable=True))
    op.add_column('documentos', sa.Column('motivo_retirada', sa.Text(), nullable=True))


def downgrade() -> None:
    """Quita las columnas de la retirada."""
    # batch: SQLite antiguo no soporta DROP COLUMN (en PostgreSQL es un ALTER normal)
    with op.batch_alter_table('documentos') as batch:
        batch.drop_column('motivo_retirada')
        batch.drop_column('retirado_por')
        batch.drop_column('retirado_en')
