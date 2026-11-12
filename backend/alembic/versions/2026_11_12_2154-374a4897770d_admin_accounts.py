"""admin accounts

Revision ID: 374a4897770d
Revises: 7f89aabbe5bf
Create Date: 2026-11-12 21:54:15.349158

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "374a4897770d"
down_revision: str | Sequence[str] | None = "7f89aabbe5bf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Admins create accounts (#66); existing users aren't admins
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "is_admin")
