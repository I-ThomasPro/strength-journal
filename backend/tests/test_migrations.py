"""Data migrations, each run inside a transaction that's rolled back afterwards"""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, text

from tests.conftest import ALEMBIC_INI, TEST_DATABASE_URL

BEFORE_SLOTS = "0f652258164a"
SLOTS = "83e34e0478bc"
CYCLES = "e85f55a6a584"
SET_RECORDS_IN_SESSIONS = "c379d18a8b36"


@pytest.fixture
def migration(engine: Engine) -> Iterator[tuple[Connection, Config]]:
    """A connection in a transaction, and an Alembic config that migrates it. Postgres DDL is
    transactional, so the rollback afterwards undoes every migration the test runs"""
    with engine.connect() as connection:
        transaction = connection.begin()
        config = Config(str(ALEMBIC_INI))
        config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL.replace("%", "%%"))
        config.attributes["connection"] = connection
        try:
            yield connection, config
        finally:
            transaction.rollback()


def test_each_workout_becomes_a_slot_at_its_old_position_and_back(
    migration: tuple[Connection, Config],
) -> None:
    connection, config = migration
    command.downgrade(config, BEFORE_SLOTS)
    routine, other_routine = uuid.uuid4(), uuid.uuid4()
    day_a, day_b, other_day = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    connection.execute(
        text("INSERT INTO routines (id, name) VALUES (:a, 'Routine'), (:b, 'Other')"),
        {"a": routine, "b": other_routine},
    )
    connection.execute(
        text(
            "INSERT INTO workouts (id, routine_id, name, position) VALUES "
            "(:b, :r, 'Day B', 1), (:a, :r, 'Day A', 0), (:o, :other, 'Other day', 0)"
        ),
        {"a": day_a, "b": day_b, "o": other_day, "r": routine, "other": other_routine},
    )

    command.upgrade(config, SLOTS)

    slots = connection.execute(
        text(
            "SELECT routine_id, workout_id, position FROM routine_workouts "
            "ORDER BY routine_id = :r DESC, position"
        ),
        {"r": routine},
    ).all()
    assert [tuple(slot) for slot in slots] == [
        (routine, day_a, 0),
        (routine, day_b, 1),
        (other_routine, other_day, 0),
    ]

    # Repeat Day A at the end of the cycle and add a Day C that isn't in it, then go back:
    # each workout takes its first slot's place, and Day C goes last
    day_c = uuid.uuid4()
    connection.execute(
        text("INSERT INTO workouts (id, routine_id, name) VALUES (:c, :r, 'Day C')"),
        {"c": day_c, "r": routine},
    )
    connection.execute(
        text(
            "INSERT INTO routine_workouts (id, routine_id, workout_id, position) "
            "VALUES (:id, :r, :a, 2)"
        ),
        {"id": uuid.uuid4(), "r": routine, "a": day_a},
    )

    command.downgrade(config, BEFORE_SLOTS)

    workouts = connection.execute(
        text("SELECT name, position FROM workouts WHERE routine_id = :r ORDER BY position"),
        {"r": routine},
    ).all()
    assert [tuple(workout) for workout in workouts] == [("Day A", 0), ("Day B", 1), ("Day C", 2)]


def test_every_existing_routine_starts_at_an_open_cycle_one(
    migration: tuple[Connection, Config],
) -> None:
    connection, config = migration
    command.downgrade(config, SLOTS)
    routines = [uuid.uuid4(), uuid.uuid4()]
    connection.execute(
        text("INSERT INTO routines (id, name) VALUES (:a, 'Library'), (:b, 'Another')"),
        {"a": routines[0], "b": routines[1]},
    )

    command.upgrade(config, CYCLES)

    cycles = connection.execute(
        text(
            "SELECT routine_id, number, completed_at FROM routine_cycles "
            "WHERE routine_id IN (:a, :b) ORDER BY routine_id"
        ),
        {"a": routines[0], "b": routines[1]},
    ).all()
    assert sorted(tuple(cycle) for cycle in cycles) == sorted(
        (routine, 1, None) for routine in routines
    )


def test_existing_set_records_are_grouped_into_daily_sessions_and_back(
    migration: tuple[Connection, Config],
) -> None:
    connection, config = migration
    command.downgrade(config, CYCLES)
    lifter, other_lifter, exercise = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    connection.execute(
        text(
            "INSERT INTO users (id, email, password_hash, display_name) VALUES "
            "(:a, :a_email, 'x', 'A'), (:b, :b_email, 'x', 'B')"
        ),
        {
            "a": lifter,
            "b": other_lifter,
            "a_email": f"{lifter}@x.test",
            "b_email": f"{other_lifter}@x.test",
        },
    )
    connection.execute(
        text("INSERT INTO exercises (id, name) VALUES (:e, :n)"),
        {"e": exercise, "n": f"Lift {exercise}"},
    )
    monday = datetime(2026, 11, 2, 18, 0, tzinfo=UTC)
    rows = [
        # (user, reps, performed_at): two on Monday out of order, one on Tuesday
        (lifter, 3, monday + timedelta(minutes=5)),
        (lifter, 5, monday),
        (lifter, 1, monday + timedelta(days=1)),
        (other_lifter, 8, monday),
    ]
    for user, reps, performed_at in rows:
        connection.execute(
            text(
                "INSERT INTO set_records (id, user_id, exercise_id, reps, weight, weight_unit, "
                "performed_at) VALUES (:id, :u, :e, :r, 60, 'kg', :at)"
            ),
            {"id": uuid.uuid4(), "u": user, "e": exercise, "r": reps, "at": performed_at},
        )
    # Run the inserts' deferred foreign-key checks now and go back to deferred mode, so the
    # migration starts as it would in its own transaction: Postgres won't ALTER a table
    # with checks still pending
    connection.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
    connection.execute(text("SET CONSTRAINTS ALL DEFERRED"))

    command.upgrade(config, SET_RECORDS_IN_SESSIONS)

    sessions = connection.execute(
        text(
            "SELECT s.user_id, s.performed_at, s.completed, s.routine_workout_id, "
            "array_agg(r.reps ORDER BY r.position) "
            "FROM workout_sessions s JOIN set_records r ON r.session_id = s.id "
            "WHERE s.user_id IN (:a, :b) "
            "GROUP BY s.id ORDER BY s.user_id = :a DESC, s.performed_at"
        ),
        {"a": lifter, "b": other_lifter},
    ).all()
    assert [tuple(session) for session in sessions] == [
        (lifter, monday, True, None, [5, 3]),
        (lifter, monday + timedelta(days=1), True, None, [1]),
        (other_lifter, monday, True, None, [8]),
    ]

    command.downgrade(config, CYCLES)

    restored = connection.execute(
        text(
            "SELECT user_id, reps, performed_at FROM set_records "
            "WHERE user_id = :a ORDER BY performed_at"
        ),
        {"a": lifter},
    ).all()
    # Each record gets its session's time, a microsecond apart in position order
    assert [tuple(row) for row in restored] == [
        (lifter, 5, monday),
        (lifter, 3, monday + timedelta(microseconds=1)),
        (lifter, 1, monday + timedelta(days=1)),
    ]
