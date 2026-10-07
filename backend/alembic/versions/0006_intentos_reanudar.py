"""documentos.intentos_reanudar: veces que el arranque ha relanzado un analisis interrumpido.

Al superar MAX_REINTENTOS_REANUDAR, el documento pasa a error (ingesta.servicio.reanudar_pendientes); un
analisis que termina lo vuelve a 0.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Anade documentos.intentos_reanudar (NOT NULL; las filas existentes quedan en 0)."""
    op.add_column('documentos', sa.Column('intentos_reanudar', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    """Quita documentos.intentos_reanudar."""
    # batch: SQLite antiguo no soporta DROP COLUMN (en PostgreSQL es un ALTER normal)
    with op.batch_alter_table('documentos') as batch:
        batch.drop_column('intentos_reanudar')
