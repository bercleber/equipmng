"""seed roles

Revision ID: 4e81d0c39a16
Revises: 5ca6f345e298
Create Date: 2026-09-07 17:18:32.303496

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4e81d0c39a16"
down_revision: Union[str, Sequence[str], None] = "5ca6f345e298"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

role_table = sa.table(
    "role",
    sa.column("name", sa.String(length=14)),
    sa.column("description", sa.String(length=300)),
)


def upgrade() -> None:
    """Insert the application's default roles."""
    op.bulk_insert(
        role_table,
        [
            {
                "name": "ADMINISTRADOR",
                "description": "Administrador do sistema",
            },
            {
                "name": "GESTOR",
                "description": "Gestor de empréstimos",
            },
            {
                "name": "ALUNO",
                "description": "Aluno solicitante",
            },
        ],
    )


def downgrade() -> None:
    """Remove the application's default roles."""
    op.execute(
        role_table.delete().where(
            role_table.c.name.in_(["ADMINISTRADOR", "GESTOR", "ALUNO"])
        )
    )
