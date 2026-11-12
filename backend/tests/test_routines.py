"""Library and user routines, and the routine detail"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.models.exercise import Exercise
from app.models.routine import Routine
from app.models.set import Set
from app.models.set_record import SetRecord
from app.models.user import User
from app.models.workout import Workout, WorkoutExercise
from tests.factories import (
    create_exercise,
    create_routine,
    create_routine_workout,
    create_set,
    create_set_record,
    create_user,
    create_workout,
    create_workout_exercise,
)
from tests.helpers import assert_error


def names(body: dict) -> list[str]:
    return [item["name"] for item in body["items"]]


def count(db_session: Session, model: type, **filters: object) -> int:
    statement = select(func.count()).select_from(model).filter_by(**filters)
    return db_session.scalar(statement) or 0


@contextmanager
def counting_queries(db_session: Session) -> Iterator[list[str]]:
    """Collect the SQL statements run on the test's connection"""
    statements: list[str] = []
    connection = db_session.connection()

    def record(_conn: object, _cursor: object, statement: str, *_args: object) -> None:
        statements.append(statement)

    event.listen(connection, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(connection, "before_cursor_execute", record)


def build_routine(db_session: Session, owner: User, size: int) -> Routine:
    """A routine with `size` workouts, each with `size` exercises of `size` sets, and a cycle
    of `size` slots per workout"""
    routine = create_routine(db_session, owner=owner)
    for _ in range(size):
        workout = create_workout(db_session, routine)
        for _ in range(size):
            create_routine_workout(db_session, workout)
        for _ in range(size):
            exercise = create_exercise(db_session, owner=owner)
            workout_exercise = create_workout_exercise(db_session, workout, exercise)
            for _ in range(size):
                create_set(db_session, workout_exercise)
    return routine


# Index


@pytest.fixture
def mixed_routines(db_session: Session, current_user: User) -> None:
    """Two library routines, two of the current user's, and one of another user's"""
    create_routine(db_session, name="Starting Strength")
    create_routine(db_session, name="5/3/1")
    mine = create_routine(db_session, name="my push pull legs", owner=current_user)
    create_routine(db_session, name="Accessories", owner=current_user)
    create_routine(db_session, name="Their routine", owner=create_user(db_session))
    for _ in range(3):
        create_workout(db_session, mine)


@pytest.mark.usefixtures("mixed_routines")
@pytest.mark.parametrize(
    ("scope", "expected"),
    [
        ("all", ["5/3/1", "Accessories", "my push pull legs", "Starting Strength"]),
        ("library", ["5/3/1", "Starting Strength"]),
        ("mine", ["Accessories", "my push pull legs"]),
    ],
)
def test_each_scope_lists_its_routines_by_name(
    logged_in_client: TestClient, scope: str, expected: list[str]
) -> None:
    response = logged_in_client.get("/api/routines", params={"scope": scope})

    assert response.status_code == 200, response.text
    body = response.json()
    assert names(body) == expected
    assert body["total"] == len(expected)


@pytest.mark.usefixtures("mixed_routines")
def test_routine_summaries(logged_in_client: TestClient, db_session: Session) -> None:
    items = logged_in_client.get("/api/routines").json()["items"]

    by_name = {item["name"]: item for item in items}
    mine = by_name["my push pull legs"]
    assert mine["workout_count"] == 3
    assert mine["is_library"] is False
    assert mine["description"] is None
    assert mine["source_routine_id"] is None
    assert by_name["Accessories"]["workout_count"] == 0
    assert by_name["5/3/1"]["is_library"] is True


def test_a_copy_shows_its_source(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    source = create_routine(db_session, name="Library original")
    create_routine(db_session, name="My copy", owner=current_user, source_routine=source)

    items = logged_in_client.get("/api/routines", params={"scope": "mine"}).json()["items"]

    assert items[0]["source_routine_id"] == str(source.id)


# Create


def test_creating_an_empty_routine(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    response = logged_in_client.post(
        "/api/routines", json={"name": "  Upper Lower  ", "description": "Four days a week"}
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Upper Lower"
    assert body["description"] == "Four days a week"
    assert body["is_library"] is False
    assert body["workouts"] == []
    routine = db_session.get(Routine, uuid.UUID(body["id"]))
    assert routine is not None and routine.owner_id == current_user.id


def test_a_blank_description_is_stored_as_none(logged_in_client: TestClient) -> None:
    body = logged_in_client.post("/api/routines", json={"name": "A", "description": "  "}).json()

    assert body["description"] is None


@pytest.mark.parametrize(
    "body", [{}, {"name": "  "}, {"name": "x" * 101}, {"name": "A", "description": "x" * 2001}]
)
def test_invalid_routines_are_rejected(logged_in_client: TestClient, body: dict) -> None:
    assert_error(logged_in_client.post("/api/routines", json=body), 422, "invalid")


# Show


def test_the_detail_returns_everything_in_position_order(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    routine = create_routine(db_session, owner=current_user)
    squat = create_exercise(db_session, name="Squat")
    bench = create_exercise(db_session, name="Bench Press", owner=current_user)
    # Workouts are listed in the order they were added; the other levels are created out of
    # order (later positions first)
    added = datetime(2026, 1, 1, tzinfo=UTC)
    day_b = create_workout(db_session, routine, name="Day B", created_at=added + timedelta(1))
    day_a = create_workout(db_session, routine, name="Day A", created_at=added)
    create_routine_workout(db_session, day_a, position=2)
    create_routine_workout(db_session, day_b, position=1)
    create_routine_workout(db_session, day_a, position=0)
    second = create_workout_exercise(db_session, day_a, bench, position=1)
    first = create_workout_exercise(db_session, day_a, squat, position=0)
    create_workout_exercise(db_session, day_b, squat, position=0)
    create_set(db_session, first, position=1, target_reps=3)
    create_set(db_session, first, position=0, target_reps=5)
    db_session.expire_all()

    response = logged_in_client.get(f"/api/routines/{routine.id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert [workout["name"] for workout in body["workouts"]] == ["Day A", "Day B"]
    assert "position" not in body["workouts"][0]
    assert [(slot["position"], slot["workout"]) for slot in body["slots"]] == [
        (0, {"id": str(day_a.id), "name": "Day A"}),
        (1, {"id": str(day_b.id), "name": "Day B"}),
        (2, {"id": str(day_a.id), "name": "Day A"}),
    ]
    exercises = body["workouts"][0]["exercises"]
    assert [entry["id"] for entry in exercises] == [str(first.id), str(second.id)]
    assert exercises[0]["exercise"] == {"id": str(squat.id), "name": "Squat", "type": "strength"}
    assert exercises[0]["position"] == 0
    assert [entry["target_reps"] for entry in exercises[0]["sets"]] == [5, 3]
    assert exercises[0]["sets"][0]["target_weight"] == "60.00"
    assert exercises[1]["sets"] == []
    # Progressions were removed (#42); the detail no longer has them
    assert "progressions" not in body


def test_the_detail_loads_in_a_fixed_number_of_queries(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    small = build_routine(db_session, current_user, size=1)
    large = build_routine(db_session, current_user, size=3)
    query_counts = []

    for routine in [small, large]:
        db_session.expire_all()
        with counting_queries(db_session) as statements:
            response = logged_in_client.get(f"/api/routines/{routine.id}")
        assert response.status_code == 200
        query_counts.append(len(statements))

    assert len(response.json()["workouts"]) == 3
    assert query_counts[0] == query_counts[1], query_counts


def test_library_routines_are_visible(logged_in_client: TestClient, db_session: Session) -> None:
    library = create_routine(db_session, name="Starting Strength")

    response = logged_in_client.get(f"/api/routines/{library.id}")

    assert response.status_code == 200
    assert response.json()["is_library"] is True


def test_another_users_routine_is_not_found(
    logged_in_client: TestClient, db_session: Session
) -> None:
    theirs = create_routine(db_session, owner=create_user(db_session))

    assert_error(logged_in_client.get(f"/api/routines/{theirs.id}"), 404, "not_found")
    assert_error(logged_in_client.get(f"/api/routines/{uuid.uuid4()}"), 404, "not_found")
    assert names(logged_in_client.get("/api/routines").json()) == []


# Update


def test_updating_a_routine(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    routine = create_routine(db_session, name="Old", description="Old notes", owner=current_user)
    create_workout(db_session, routine, name="Day A")
    path = f"/api/routines/{routine.id}"

    renamed = logged_in_client.patch(path, json={"name": "New"})
    cleared = logged_in_client.patch(path, json={"description": None})

    assert renamed.status_code == 200, renamed.text
    assert (renamed.json()["name"], renamed.json()["description"]) == ("New", "Old notes")
    assert [workout["name"] for workout in renamed.json()["workouts"]] == ["Day A"]
    assert (cleared.json()["name"], cleared.json()["description"]) == ("New", None)


def test_a_routine_name_cant_be_null(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    routine = create_routine(db_session, owner=current_user)

    response = logged_in_client.patch(f"/api/routines/{routine.id}", json={"name": None})

    assert_error(response, 422, "invalid")


def test_library_routines_cant_be_changed(
    logged_in_client: TestClient, db_session: Session
) -> None:
    library = create_routine(db_session, name="Starting Strength")
    path = f"/api/routines/{library.id}"

    assert_error(logged_in_client.patch(path, json={"name": "Mine now"}), 403, "read_only")
    assert_error(logged_in_client.delete(path), 403, "read_only")
    db_session.expire_all()
    assert db_session.get(Routine, library.id).name == "Starting Strength"


def test_another_users_routine_cant_be_changed(
    logged_in_client: TestClient, db_session: Session
) -> None:
    theirs = create_routine(db_session, name="Theirs", owner=create_user(db_session))
    path = f"/api/routines/{theirs.id}"

    assert_error(logged_in_client.patch(path, json={"name": "Mine now"}), 404, "not_found")
    assert_error(logged_in_client.delete(path), 404, "not_found")
    db_session.expire_all()
    assert db_session.get(Routine, theirs.id).name == "Theirs"


# Destroy


def test_deleting_a_routine_keeps_its_exercises_and_set_records(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    routine = build_routine(db_session, current_user, size=2)
    other = build_routine(db_session, current_user, size=1)
    exercises = count(db_session, Exercise, owner_id=current_user.id)
    exercise = db_session.scalars(select(Exercise).where(Exercise.owner == current_user)).first()
    record = create_set_record(db_session, user=current_user, exercise=exercise)

    response = logged_in_client.delete(f"/api/routines/{routine.id}")

    assert response.status_code == 204, response.text
    db_session.expire_all()
    assert db_session.get(Routine, routine.id) is None
    assert count(db_session, Workout, routine_id=routine.id) == 0
    # Only the other routine's workout exercise and set are left
    assert count(db_session, WorkoutExercise) == 1
    assert count(db_session, Set) == 1
    assert db_session.get(Routine, other.id) is not None
    assert count(db_session, Exercise, owner_id=current_user.id) == exercises
    assert db_session.get(SetRecord, record.id) is not None


def test_routines_need_a_login(client: TestClient) -> None:
    assert_error(client.get("/api/routines"), 401, "not_authenticated")
