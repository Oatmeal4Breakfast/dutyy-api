"""add publishing status server default

Revision ID: b72e4c9a1d03
Revises: 4a9c3b2a3e6f
Create Date: 2026-11-24 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b72e4c9a1d03"
down_revision: Union[str, Sequence[str], None] = "4a9c3b2a3e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Allow project inserts that omit the legacy publishing status."""
    op.alter_column(
        "projects",
        "publishing_status",
        existing_type=sa.Enum("DRAFT", "PUBLISHED", name="publishingstatus"),
        existing_nullable=False,
        server_default=sa.text("'DRAFT'::publishingstatus"),
    )


def downgrade() -> None:
    """Restore the publishing status column without a server default."""
    op.alter_column(
        "projects",
        "publishing_status",
        existing_type=sa.Enum("DRAFT", "PUBLISHED", name="publishingstatus"),
        existing_nullable=False,
        server_default=None,
    )
