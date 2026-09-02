"""add: status to apikey table

Revision ID: 0f8c29054502
Revises: a127b65a5a2b
Create Date: 2026-06-20 19:35:10.561802

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0f8c29054502"
down_revision: Union[str, Sequence[str], None] = "a127b65a5a2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    apikeystatus = sa.Enum("ACTIVE", "INACTIVE", name="apikeystatus")
    apikeystatus.create(op.get_bind())
    op.add_column(
        "api_keys",
        sa.Column("status", apikeystatus, nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("api_keys", "status")
    sa.Enum(name="apikeystatus").drop(op.get_bind())
