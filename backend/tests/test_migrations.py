"""Data migrations, each run inside a transaction that's rolled back afterwards"""

import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, Engine, text

from tests.conftest import ALEMBIC_INI, TEST_DATABASE_URL

BEFORE_SLOTS = "0f652258164a"
SLOTS = "83e34e0478bc"


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
