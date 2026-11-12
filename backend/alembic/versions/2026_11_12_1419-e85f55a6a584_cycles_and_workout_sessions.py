"""cycles and workout sessions

Revision ID: e85f55a6a584
Revises: 83e34e0478bc
Create Date: 2026-11-12 14:19:22.961405

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e85f55a6a584"
down_revision: str | Sequence[str] | None = "83e34e0478bc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "routine_cycles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("routine_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("number >= 1", name=op.f("ck_routine_cycles_number_positive")),
        sa.ForeignKeyConstraint(
            ["routine_id"],
            ["routines.id"],
            name=op.f("fk_routine_cycles_routine_id_routines"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_routine_cycles")),
        sa.UniqueConstraint("routine_id", "number", name="uq_routine_cycles_routine_id_number"),
    )
    op.create_index(
        "uq_routine_cycles_routine_id_open",
        "routine_cycles",
        ["routine_id"],
        unique=True,
        postgresql_where=sa.text("completed_at IS NULL"),
    )
    # Every existing routine starts at an open cycle 1, as new and copied ones do (#44)
    op.execute(
        "INSERT INTO routine_cycles (id, routine_id, number) "
        "SELECT gen_random_uuid(), id, 1 FROM routines"
    )
    op.create_table(
        "workout_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("routine_workout_id", sa.Uuid(), nullable=True),
        sa.Column("workout_id", sa.Uuid(), nullable=True),
        sa.Column("cycle_id", sa.Uuid(), nullable=True),
        sa.Column(
            "performed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["cycle_id"],
            ["routine_cycles.id"],
            name=op.f("fk_workout_sessions_cycle_id_routine_cycles"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["routine_workout_id"],
            ["routine_workouts.id"],
            name=op.f("fk_workout_sessions_routine_workout_id_routine_workouts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_workout_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workout_id"],
            ["workouts.id"],
            name=op.f("fk_workout_sessions_workout_id_workouts"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workout_sessions")),
    )
    op.create_index(
        op.f("ix_workout_sessions_cycle_id"), "workout_sessions", ["cycle_id"], unique=False
    )
    op.create_index(
        op.f("ix_workout_sessions_routine_workout_id"),
        "workout_sessions",
        ["routine_workout_id"],
        unique=False,
    )
    op.create_index(
        "ix_workout_sessions_user_id_performed_at",
        "workout_sessions",
        ["user_id", "performed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workout_sessions_workout_id"), "workout_sessions", ["workout_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_workout_sessions_workout_id"), table_name="workout_sessions")
    op.drop_index("ix_workout_sessions_user_id_performed_at", table_name="workout_sessions")
    op.drop_index(op.f("ix_workout_sessions_routine_workout_id"), table_name="workout_sessions")
    op.drop_index(op.f("ix_workout_sessions_cycle_id"), table_name="workout_sessions")
    op.drop_table("workout_sessions")
    op.drop_index(
        "uq_routine_cycles_routine_id_open",
        table_name="routine_cycles",
        postgresql_where=sa.text("completed_at IS NULL"),
    )
    op.drop_table("routine_cycles")
