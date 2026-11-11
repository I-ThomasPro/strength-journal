"""How a routine's exercises gain weight: creating, changing and protecting progressions"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.common import WeightUnit
from app.models.exercise import Exercise
from app.models.progression import Progression
from app.models.routine import Routine
from app.models.user import User
from tests.factories import (
    create_exercise,
    create_progression,
    create_routine,
    create_user,
    create_workout,
    create_workout_exercise,
)
from tests.helpers import assert_error


def routine_with(db_session: Session, owner: User | None, *names: str) -> Routine:
    """A routine whose one workout uses a new library exercise for each name"""
    routine = create_routine(db_session, owner=owner)
    workout = create_workout(db_session, routine)
    for name in names:
        create_workout_exercise(db_session, workout, create_exercise(db_session, name=name))
    return routine


def exercise_named(db_session: Session, name: str) -> Exercise:
    return db_session.query(Exercise).filter_by(name=name).one()


@pytest.fixture
def routine(db_session: Session, current_user: User) -> Routine:
    return routine_with(db_session, current_user, "Squat", "Bench Press")


@pytest.fixture
def squat(db_session: Session, routine: Routine) -> Exercise:
    return exercise_named(db_session, "Squat")


def stored(db_session: Session, routine: Routine) -> list[Progression]:
    db_session.expire_all()
    return db_session.query(Progression).filter_by(routine_id=routine.id).all()


# Create


def test_creating_a_progression_with_the_defaults(
    logged_in_client: TestClient,
    db_session: Session,
    current_user: User,
    routine: Routine,
    squat: Exercise,
) -> None:
    current_user.weight_unit = WeightUnit.LB
    db_session.flush()

    response = logged_in_client.post(
        f"/api/routines/{routine.id}/progressions",
        json={"exercise_id": str(squat.id), "increment": "5"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["exercise"] == {"id": str(squat.id), "name": "Squat", "type": "strength"}
    assert body["routine_id"] == str(routine.id)
    assert body["increment"] == "5.00"
    assert body["increment_unit"] == "lb"
    assert body["condition"] == "all_sets_completed"
    assert [p.id for p in stored(db_session, routine)] == [uuid.UUID(body["id"])]


def test_creating_a_progression_with_every_field(
    logged_in_client: TestClient, routine: Routine, squat: Exercise
) -> None:
    response = logged_in_client.post(
        f"/api/routines/{routine.id}/progressions",
        json={
            "exercise_id": str(squat.id),
            "increment": 2.5,
            "increment_unit": "kg",
            "condition": "all_sets_completed",
        },
    )

    assert response.status_code == 201, response.text
    assert (response.json()["increment"], response.json()["increment_unit"]) == ("2.50", "kg")


def test_a_second_progression_for_an_exercise_is_a_409(
    logged_in_client: TestClient, db_session: Session, routine: Routine, squat: Exercise
) -> None:
    create_progression(db_session, routine=routine, exercise=squat)

    response = logged_in_client.post(
        f"/api/routines/{routine.id}/progressions",
        json={"exercise_id": str(squat.id), "increment": "1"},
    )

    assert_error(response, 409, "duplicate_progression")
    assert len(stored(db_session, routine)) == 1


def test_an_exercise_not_in_the_routine_is_rejected(
    logged_in_client: TestClient, db_session: Session, routine: Routine
) -> None:
    elsewhere = routine_with(db_session, None, "Deadlift")
    path = f"/api/routines/{routine.id}/progressions"

    for exercise_id in [exercise_named(db_session, "Deadlift").id, uuid.uuid4()]:
        response = logged_in_client.post(
            path, json={"exercise_id": str(exercise_id), "increment": "1"}
        )
        assert_error(response, 422, "invalid")
    assert stored(db_session, routine) == []
    assert stored(db_session, elsewhere) == []


@pytest.mark.parametrize(
    "change",
    [
        {"increment": "0"},
        {"increment": "-2.5"},
        {"increment": "abc"},
        {"increment": "1.234"},
        {"increment": "10000"},
        {"increment_unit": "stone"},
        {"condition": "whenever"},
    ],
)
def test_invalid_progressions_are_rejected(
    logged_in_client: TestClient, routine: Routine, squat: Exercise, change: dict
) -> None:
    body = {"exercise_id": str(squat.id), "increment": "2.5"} | change

    response = logged_in_client.post(f"/api/routines/{routine.id}/progressions", json=body)

    assert_error(response, 422, "invalid")


# Reading


def test_listing_a_routines_progressions(
    logged_in_client: TestClient, db_session: Session, routine: Routine, squat: Exercise
) -> None:
    first = create_progression(db_session, routine=routine, exercise=squat)
    bench = exercise_named(db_session, "Bench Press")
    second = create_progression(db_session, routine=routine, exercise=bench)

    body = logged_in_client.get(f"/api/routines/{routine.id}/progressions").json()

    assert {item["id"] for item in body["items"]} == {str(first.id), str(second.id)}
    assert body["total"] == 2
    assert {item["exercise"]["name"] for item in body["items"]} == {"Squat", "Bench Press"}


def test_library_routines_progressions_can_be_read(
    logged_in_client: TestClient, db_session: Session
) -> None:
    library = routine_with(db_session, None, "Overhead Press")
    progression = create_progression(
        db_session, routine=library, exercise=exercise_named(db_session, "Overhead Press")
    )

    listed = logged_in_client.get(f"/api/routines/{library.id}/progressions")
    shown = logged_in_client.get(f"/api/progressions/{progression.id}")

    assert listed.json()["total"] == 1
    assert shown.status_code == 200
    assert shown.json()["exercise"]["name"] == "Overhead Press"


def test_another_users_progressions_are_not_found(
    logged_in_client: TestClient, db_session: Session
) -> None:
    theirs = routine_with(db_session, create_user(db_session), "Row")
    progression = create_progression(
        db_session, routine=theirs, exercise=exercise_named(db_session, "Row")
    )

    assert_error(logged_in_client.get(f"/api/routines/{theirs.id}/progressions"), 404, "not_found")
    assert_error(logged_in_client.get(f"/api/progressions/{progression.id}"), 404, "not_found")
    assert_error(logged_in_client.get(f"/api/progressions/{uuid.uuid4()}"), 404, "not_found")


def test_a_new_progression_shows_in_the_routine_detail(
    logged_in_client: TestClient, routine: Routine, squat: Exercise
) -> None:
    created = logged_in_client.post(
        f"/api/routines/{routine.id}/progressions",
        json={"exercise_id": str(squat.id), "increment": "2.5"},
    ).json()

    detail = logged_in_client.get(f"/api/routines/{routine.id}").json()

    assert [p["id"] for p in detail["progressions"]] == [created["id"]]


# Update and delete


def test_updating_a_progression(
    logged_in_client: TestClient, db_session: Session, routine: Routine, squat: Exercise
) -> None:
    progression = create_progression(db_session, routine=routine, exercise=squat)
    path = f"/api/progressions/{progression.id}"

    increment = logged_in_client.patch(path, json={"increment": "1.25"})
    unit = logged_in_client.patch(path, json={"increment_unit": "lb"})

    assert increment.status_code == 200, increment.text
    assert (increment.json()["increment"], increment.json()["increment_unit"]) == ("1.25", "kg")
    assert (unit.json()["increment"], unit.json()["increment_unit"]) == ("1.25", "lb")
    assert unit.json()["exercise"]["name"] == "Squat"


@pytest.mark.parametrize(
    "change",
    [{"increment": None}, {"increment": "0"}, {"increment_unit": None}, {"condition": None}],
)
def test_invalid_progression_updates_are_rejected(
    logged_in_client: TestClient,
    db_session: Session,
    routine: Routine,
    squat: Exercise,
    change: dict,
) -> None:
    progression = create_progression(db_session, routine=routine, exercise=squat)

    response = logged_in_client.patch(f"/api/progressions/{progression.id}", json=change)

    assert_error(response, 422, "invalid")


def test_deleting_a_progression(
    logged_in_client: TestClient, db_session: Session, routine: Routine, squat: Exercise
) -> None:
    progression = create_progression(db_session, routine=routine, exercise=squat)

    response = logged_in_client.delete(f"/api/progressions/{progression.id}")

    assert response.status_code == 204, response.text
    assert stored(db_session, routine) == []
    assert db_session.get(Exercise, squat.id) is not None


# Library and other users' routines are protected


@pytest.mark.parametrize(
    ("owner", "status_code", "code"),
    [("library", 403, "read_only"), ("someone else", 404, "not_found")],
)
def test_progressions_of_routines_that_arent_yours_cant_be_changed(
    logged_in_client: TestClient, db_session: Session, owner: str, status_code: int, code: str
) -> None:
    user = None if owner == "library" else create_user(db_session)
    routine = routine_with(db_session, user, "Squat", "Dip")
    progression = create_progression(
        db_session, routine=routine, exercise=exercise_named(db_session, "Squat")
    )
    dip = exercise_named(db_session, "Dip")
    path = f"/api/progressions/{progression.id}"

    responses = [
        logged_in_client.post(
            f"/api/routines/{routine.id}/progressions",
            json={"exercise_id": str(dip.id), "increment": "1"},
        ),
        logged_in_client.patch(path, json={"increment": "10"}),
        logged_in_client.delete(path),
    ]

    for response in responses:
        assert_error(response, status_code, code)
    [kept] = stored(db_session, routine)
    assert kept.increment == progression.increment


def test_progressions_need_a_login(client: TestClient, routine: Routine) -> None:
    assert_error(client.get(f"/api/routines/{routine.id}/progressions"), 401, "not_authenticated")
