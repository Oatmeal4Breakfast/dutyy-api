"""new enum for api keys

Revision ID: 4a9c3b2a3e6f
Revises: 3feac35f8f12
Create Date: 2026-11-24 13:08:10.486120

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4a9c3b2a3e6f"
down_revision: Union[str, Sequence[str], None] = "3feac35f8f12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE apikeystatus ADD VALUE IF NOT EXISTS 'EXPIRED'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE api_keys SET status = 'INACTIVE' WHERE status = 'EXPIRED'")
    op.drop_index("uq_api_keys_active_name", table_name="api_keys")
    op.execute("ALTER TYPE apikeystatus RENAME TO apikeystatus_with_expired")
    op.execute("CREATE TYPE apikeystatus AS ENUM ('ACTIVE', 'INACTIVE')")
    op.execute(
        """
        ALTER TABLE api_keys
        ALTER COLUMN status TYPE apikeystatus
        USING status::text::apikeystatus
        """
    )
    op.execute("DROP TYPE apikeystatus_with_expired")
    op.create_index(
        "uq_api_keys_active_name",
        "api_keys",
        ["user_id", "name"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
