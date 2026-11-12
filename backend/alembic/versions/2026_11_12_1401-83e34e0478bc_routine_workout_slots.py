"""routine workout slots

Revision ID: 83e34e0478bc
Revises: 0f652258164a
Create Date: 2026-11-12 14:01:33.310812

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "83e34e0478bc"
down_revision: str | Sequence[str] | None = "0f652258164a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # A routine's cycle moves into slots, so a workout can come at several positions (#43).
    # The composite foreign key below needs (routine_id, id) to be unique on workouts first
    op.create_unique_constraint("uq_workouts_routine_id_id", "workouts", ["routine_id", "id"])
    op.create_table(
        "routine_workouts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("routine_id", sa.Uuid(), nullable=False),
        sa.Column("workout_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("position >= 0", name=op.f("ck_routine_workouts_position_non_negative")),
        sa.ForeignKeyConstraint(
            ["routine_id", "workout_id"],
            ["workouts.routine_id", "workouts.id"],
            name="fk_routine_workouts_routine_id_workout_id_workouts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["routine_id"],
            ["routines.id"],
            name=op.f("fk_routine_workouts_routine_id_routines"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_routine_workouts")),
        sa.UniqueConstraint(
            "routine_id",
            "position",
            deferrable=True,
            initially="DEFERRED",
            name="uq_routine_workouts_routine_id_position",
        ),
    )
    op.create_index(
        "ix_routine_workouts_workout_id", "routine_workouts", ["workout_id"], unique=False
    )
    # Each existing workout fills one slot, at its old position
    op.execute(
        """
        INSERT INTO routine_workouts (id, routine_id, workout_id, position)
        SELECT gen_random_uuid(), routine_id, id, position FROM workouts
        """
    )
    # Dropping the column also drops ck_workouts_position_non_negative
    op.drop_constraint(op.f("uq_workouts_routine_id_position"), "workouts", type_="unique")
    op.drop_column("workouts", "position")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("workouts", sa.Column("position", sa.Integer(), nullable=True))
    # Each workout goes back to its first slot's place in the cycle; workouts in no slot go
    # last. Numbered 0, 1, 2... per routine, as positions were before
    op.execute(
        """
        UPDATE workouts SET position = numbered.position
        FROM (
            SELECT w.id,
                   ROW_NUMBER() OVER (
                       PARTITION BY w.routine_id
                       ORDER BY MIN(rw.position) NULLS LAST, w.created_at, w.id
                   ) - 1 AS position
            FROM workouts w
            LEFT JOIN routine_workouts rw ON rw.workout_id = w.id
            GROUP BY w.id, w.routine_id, w.created_at
        ) AS numbered
        WHERE workouts.id = numbered.id
        """
    )
    op.alter_column("workouts", "position", nullable=False)
    op.create_check_constraint(
        op.f("ck_workouts_position_non_negative"), "workouts", "position >= 0"
    )
    op.create_unique_constraint(
        op.f("uq_workouts_routine_id_position"),
        "workouts",
        ["routine_id", "position"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.drop_index("ix_routine_workouts_workout_id", table_name="routine_workouts")
    op.drop_table("routine_workouts")
    op.drop_constraint("uq_workouts_routine_id_id", "workouts", type_="unique")
