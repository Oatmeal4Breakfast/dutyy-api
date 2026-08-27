"""add two non-nullable columns key_name and ttl to the device_auth_code table

Revision ID: 26ec71c9b291
Revises: 928bacee38d6
Create Date: 2026-08-26 22:50:47.030613

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "26ec71c9b291"
down_revision: Union[str, Sequence[str], None] = "928bacee38d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    keylifetime = sa.Enum("THIRTY_DAYS", "NINETY_DAYS", "ONE_YEAR", name="keylifetime")
    keylifetime.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "device_auth_code", sa.Column("key_name", sa.String(), nullable=False)
    )
    op.add_column(
        "device_auth_code", sa.Column("key_lifetime", keylifetime, nullable=False)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("device_auth_code", "key_lifetime")
    op.drop_column("device_auth_code", "key_name")
    sa.Enum(name="keylifetime").drop(op.get_bind())
