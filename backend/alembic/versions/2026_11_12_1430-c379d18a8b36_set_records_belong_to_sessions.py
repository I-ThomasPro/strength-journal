"""set records belong to sessions

Revision ID: c379d18a8b36
Revises: e85f55a6a584
Create Date: 2026-11-12 14:30:41.893581

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c379d18a8b36"
down_revision: str | Sequence[str] | None = "e85f55a6a584"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # A set record now belongs to a workout session, which carries its owner and time (#45)
    op.add_column("set_records", sa.Column("session_id", sa.Uuid(), nullable=True))
    op.add_column("set_records", sa.Column("set_id", sa.Uuid(), nullable=True))
    op.add_column("set_records", sa.Column("position", sa.Integer(), nullable=True))
    op.add_column("set_records", sa.Column("target_reps", sa.Integer(), nullable=True))
    op.add_column(
        "set_records", sa.Column("target_weight", sa.Numeric(precision=6, scale=2), nullable=True)
    )
    op.add_column("set_records", sa.Column("target_unit", sa.Text(), nullable=True))

    # Existing records become completed freestyle sessions: one per user per UTC day, dated
    # by its earliest record, with the records in performed_at order
    op.execute(
        """
        CREATE TEMPORARY TABLE set_record_days ON COMMIT DROP AS
        SELECT user_id,
               (performed_at AT TIME ZONE 'UTC')::date AS day,
               gen_random_uuid() AS session_id,
               MIN(performed_at) AS performed_at
        FROM set_records
        GROUP BY user_id, (performed_at AT TIME ZONE 'UTC')::date
        """
    )
    op.execute(
        """
        INSERT INTO workout_sessions (id, user_id, performed_at, completed)
        SELECT session_id, user_id, performed_at, true FROM set_record_days
        """
    )
    op.execute(
        """
        UPDATE set_records SET session_id = numbered.session_id, position = numbered.position
        FROM (
            SELECT r.id,
                   d.session_id,
                   ROW_NUMBER() OVER (
                       PARTITION BY d.session_id ORDER BY r.performed_at, r.id
                   ) - 1 AS position
            FROM set_records r
            JOIN set_record_days d
              ON d.user_id = r.user_id
             AND d.day = (r.performed_at AT TIME ZONE 'UTC')::date
        ) AS numbered
        WHERE set_records.id = numbered.id
        """
    )
    op.execute("DROP TABLE set_record_days")
    # The update queues set_records' deferred foreign-key checks, and Postgres won't ALTER a
    # table with checks pending, so run them now, then go back to deferring
    op.execute("SET CONSTRAINTS ALL IMMEDIATE")
    op.execute("SET CONSTRAINTS ALL DEFERRED")

    op.alter_column("set_records", "session_id", nullable=False)
    op.alter_column("set_records", "position", nullable=False)
    op.create_foreign_key(
        op.f("fk_set_records_session_id_workout_sessions"),
        "set_records",
        "workout_sessions",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_set_records_set_id_sets"),
        "set_records",
        "sets",
        ["set_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(op.f("ix_set_records_set_id"), "set_records", ["set_id"], unique=False)
    op.create_unique_constraint(
        "uq_set_records_session_id_position",
        "set_records",
        ["session_id", "position"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_check_constraint(
        op.f("ck_set_records_position_non_negative"), "set_records", "position >= 0"
    )
    op.create_check_constraint(
        op.f("ck_set_records_targets_all_or_none"),
        "set_records",
        "(target_reps IS NULL) = (target_weight IS NULL) "
        "AND (target_weight IS NULL) = (target_unit IS NULL)",
    )
    op.create_check_constraint(
        op.f("ck_set_records_target_unit"), "set_records", "target_unit IN ('kg', 'lb')"
    )

    op.drop_index(op.f("ix_set_records_user_id_exercise_id_performed_at"), table_name="set_records")
    op.drop_constraint(op.f("fk_set_records_user_id_users"), "set_records", type_="foreignkey")
    op.drop_column("set_records", "performed_at")
    op.drop_column("set_records", "user_id")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("set_records", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.add_column(
        "set_records", sa.Column("performed_at", sa.DateTime(timezone=True), nullable=True)
    )
    # The owner and time come back from each record's session. Records in one session are
    # a microsecond apart, in position order, so history keeps their order
    op.execute(
        """
        UPDATE set_records
        SET user_id = s.user_id,
            performed_at = s.performed_at + set_records.position * INTERVAL '1 microsecond'
        FROM workout_sessions s
        WHERE s.id = set_records.session_id
        """
    )
    # As in the upgrade: run the update's deferred checks before altering the table
    op.execute("SET CONSTRAINTS ALL IMMEDIATE")
    op.execute("SET CONSTRAINTS ALL DEFERRED")
    op.alter_column("set_records", "user_id", nullable=False)
    op.alter_column("set_records", "performed_at", nullable=False, server_default=sa.text("now()"))
    op.create_foreign_key(
        op.f("fk_set_records_user_id_users"),
        "set_records",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_set_records_user_id_exercise_id_performed_at"),
        "set_records",
        ["user_id", "exercise_id", "performed_at"],
        unique=False,
    )

    op.drop_constraint(op.f("ck_set_records_target_unit"), "set_records", type_="check")
    op.drop_constraint(op.f("ck_set_records_targets_all_or_none"), "set_records", type_="check")
    op.drop_constraint(op.f("ck_set_records_position_non_negative"), "set_records", type_="check")
    op.drop_constraint("uq_set_records_session_id_position", "set_records", type_="unique")
    op.drop_index(op.f("ix_set_records_set_id"), table_name="set_records")
    op.drop_constraint(op.f("fk_set_records_set_id_sets"), "set_records", type_="foreignkey")
    op.drop_constraint(
        op.f("fk_set_records_session_id_workout_sessions"), "set_records", type_="foreignkey"
    )
    op.drop_column("set_records", "target_unit")
    op.drop_column("set_records", "target_weight")
    op.drop_column("set_records", "target_reps")
    op.drop_column("set_records", "position")
    op.drop_column("set_records", "set_id")
    op.drop_column("set_records", "session_id")
