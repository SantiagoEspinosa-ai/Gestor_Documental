"""alertas.version_resultado: NULL = alerta de plataforma; N = alerta del motor de la version N.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Anade alertas.version_resultado con indice."""
    op.add_column('alertas', sa.Column('version_resultado', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_alertas_version_resultado'), 'alertas', ['version_resultado'], unique=False)


def downgrade() -> None:
    """Quita alertas.version_resultado."""
    op.drop_index(op.f('ix_alertas_version_resultado'), table_name='alertas')
    # batch: SQLite antiguo no soporta DROP COLUMN (en PostgreSQL es un ALTER normal)
    with op.batch_alter_table('alertas') as batch:
        batch.drop_column('version_resultado')
