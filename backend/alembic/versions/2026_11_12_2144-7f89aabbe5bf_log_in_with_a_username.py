"""log in with a username

Revision ID: 7f89aabbe5bf
Revises: c379d18a8b36
Create Date: 2026-11-12 21:44:05.847947

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7f89aabbe5bf"
down_revision: str | Sequence[str] | None = "c379d18a8b36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Accounts are identified by a username, not an email (#65). Renaming keeps each account's
    # email as its username, so it can still log in with what it used before
    op.alter_column("users", "email", new_column_name="username")
    # Renaming the constraint renames its index too
    op.execute("ALTER TABLE users RENAME CONSTRAINT uq_users_email TO uq_users_username")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE users RENAME CONSTRAINT uq_users_username TO uq_users_email")
    op.alter_column("users", "username", new_column_name="email")
