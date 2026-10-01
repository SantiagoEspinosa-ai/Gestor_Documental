"""correcciones.version_resultado: la correccion solo se aplica a la version del Resultado en la que se hizo.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Anade correcciones.version_resultado (NOT NULL; las filas antiguas quedan en la version 1)."""
    op.add_column('correcciones', sa.Column('version_resultado', sa.Integer(), server_default='1',
                                            nullable=False))


def downgrade() -> None:
    """Quita correcciones.version_resultado."""
    # batch: SQLite antiguo no soporta DROP COLUMN (en PostgreSQL es un ALTER normal)
    with op.batch_alter_table('correcciones') as batch:
        batch.drop_column('version_resultado')
