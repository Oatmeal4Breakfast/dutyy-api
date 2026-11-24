"""remove project publishing schema

Revision ID: c84f1a7d2e90
Revises: b72e4c9a1d03
Create Date: 2026-11-24 15:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c84f1a7d2e90"
down_revision: Union[str, Sequence[str], None] = "b72e4c9a1d03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Remove the retired project publishing state."""
    op.drop_column("projects", "published_date")
    op.drop_column("projects", "publishing_status")
    sa.Enum(name="publishingstatus").drop(op.get_bind())


def downgrade() -> None:
    """Restore publishing state with safe defaults for existing projects."""
    publishing_status = sa.Enum(
        "DRAFT",
        "PUBLISHED",
        name="publishingstatus",
    )
    publishing_status.create(op.get_bind())
    op.add_column(
        "projects",
        sa.Column(
            "publishing_status",
            publishing_status,
            nullable=False,
            server_default=sa.text("'DRAFT'::publishingstatus"),
        ),
    )
    op.add_column(
        "projects",
        sa.Column("published_date", sa.DateTime(timezone=True), nullable=True),
    )
