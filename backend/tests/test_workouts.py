"""A routine's workouts and a workout's exercises: ordering, ownership and exercise choice"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.exercise import Exercise
from app.models.routine import Routine
from app.models.set import Set
from app.models.user import User
from app.models.workout import Workout, WorkoutExercise
from tests.factories import (
    create_exercise,
    create_routine,
    create_set,
    create_user,
    create_workout,
    create_workout_exercise,
)
from tests.helpers import assert_error


@pytest.fixture
def routine(db_session: Session, current_user: User) -> Routine:
    return create_routine(db_session, owner=current_user)


def make_workouts(db_session: Session, routine: Routine, *names: str) -> list[Workout]:
    return [create_workout(db_session, routine, name=name) for name in names]


def workout_order(db_session: Session, routine: Routine) -> list[tuple[str, int]]:
    """(name, position) of the routine's workouts, as stored"""
    db_session.expire_all()
    statement = (
        select(Workout.name, Workout.position)
        .where(Workout.routine_id == routine.id)
        .order_by(Workout.position)
    )
    return [tuple(row) for row in db_session.execute(statement)]


def exercise_order(db_session: Session, workout: Workout) -> list[tuple[str, int]]:
    """(exercise name, position) of the workout's exercises, as stored"""
    db_session.expire_all()
    statement = (
        select(Exercise.name, WorkoutExercise.position)
        .join(WorkoutExercise.exercise)
        .where(WorkoutExercise.workout_id == workout.id)
        .order_by(WorkoutExercise.position)
    )
    return [tuple(row) for row in db_session.execute(statement)]


def numbered(*names: str) -> list[tuple[str, int]]:
    return [(name, position) for position, name in enumerate(names)]


# Workouts: reading


def test_listing_a_routines_workouts_in_order(
    logged_in_client: TestClient, db_session: Session, routine: Routine
) -> None:
    create_workout(db_session, routine, name="Day B", position=1)
    create_workout(db_session, routine, name="Day A", position=0)

    body = logged_in_client.get(f"/api/routines/{routine.id}/workouts").json()

    assert [(w["name"], w["position"]) for w in body["items"]] == numbered("Day A", "Day B")
    assert body["total"] == 2
    assert body["items"][0]["routine_id"] == str(routine.id)


def test_library_routines_workouts_can_be_read(
    logged_in_client: TestClient, db_session: Session
) -> None:
    (workout,) = make_workouts(db_session, create_routine(db_session), "Day A")

    listed = logged_in_client.get(f"/api/routines/{workout.routine_id}/workouts")
    shown = logged_in_client.get(f"/api/workouts/{workout.id}")

    assert listed.json()["total"] == 1
    assert shown.status_code == 200
    assert shown.json()["name"] == "Day A"


def test_another_users_workouts_are_not_found(
    logged_in_client: TestClient, db_session: Session
) -> None:
    theirs = create_routine(db_session, owner=create_user(db_session))
    (workout,) = make_workouts(db_session, theirs, "Day A")

    assert_error(logged_in_client.get(f"/api/routines/{theirs.id}/workouts"), 404, "not_found")
    assert_error(logged_in_client.get(f"/api/workouts/{workout.id}"), 404, "not_found")
    assert_error(logged_in_client.get(f"/api/workouts/{uuid.uuid4()}"), 404, "not_found")


# Workouts: adding, moving and deleting


def test_creating_appends_a_workout(
    logged_in_client: TestClient, db_session: Session, routine: Routine
) -> None:
    make_workouts(db_session, routine, "Day A")

    response = logged_in_client.post(f"/api/routines/{routine.id}/workouts", json={"name": "Day B"})

    assert response.status_code == 201, response.text
    assert response.json()["position"] == 1
    assert workout_order(db_session, routine) == numbered("Day A", "Day B")


def test_creating_at_a_position_shifts_later_workouts(
    logged_in_client: TestClient, db_session: Session, routine: Routine
) -> None:
    make_workouts(db_session, routine, "Day A", "Day C")
    path = f"/api/routines/{routine.id}/workouts"

    inserted = logged_in_client.post(path, json={"name": "Day B", "position": 1})
    past_the_end = logged_in_client.post(path, json={"name": "Day D", "position": 99})

    assert inserted.json()["position"] == 1
    assert past_the_end.json()["position"] == 3
    assert workout_order(db_session, routine) == numbered("Day A", "Day B", "Day C", "Day D")


@pytest.mark.parametrize("body", [{}, {"name": "  "}, {"name": "Day A", "position": -1}])
def test_invalid_workouts_are_rejected(
    logged_in_client: TestClient, routine: Routine, body: dict
) -> None:
    response = logged_in_client.post(f"/api/routines/{routine.id}/workouts", json=body)

    assert_error(response, 422, "invalid")


def test_renaming_a_workout(
    logged_in_client: TestClient, db_session: Session, routine: Routine
) -> None:
    _, day_b = make_workouts(db_session, routine, "Day A", "Day B")

    response = logged_in_client.patch(f"/api/workouts/{day_b.id}", json={"name": "Legs"})

    assert response.status_code == 200, response.text
    assert (response.json()["name"], response.json()["position"]) == ("Legs", 1)
    assert workout_order(db_session, routine) == numbered("Day A", "Legs")


def test_moving_a_workout_forwards_and_backwards(
    logged_in_client: TestClient, db_session: Session, routine: Routine
) -> None:
    a, _, _, d = make_workouts(db_session, routine, "A", "B", "C", "D")

    forwards = logged_in_client.patch(f"/api/workouts/{a.id}", json={"position": 2})
    assert forwards.json()["position"] == 2
    assert workout_order(db_session, routine) == numbered("B", "C", "A", "D")

    backwards = logged_in_client.patch(f"/api/workouts/{d.id}", json={"position": 0})
    assert backwards.json()["position"] == 0
    assert workout_order(db_session, routine) == numbered("D", "B", "C", "A")


def test_deleting_a_workout_closes_the_gap_and_removes_its_contents(
    logged_in_client: TestClient, db_session: Session, routine: Routine
) -> None:
    _, day_b, _ = make_workouts(db_session, routine, "Day A", "Day B", "Day C")
    entry = create_workout_exercise(db_session, day_b)
    entry_id, exercise_id = entry.id, entry.exercise_id
    create_set(db_session, entry)

    response = logged_in_client.delete(f"/api/workouts/{day_b.id}")

    assert response.status_code == 204, response.text
    assert workout_order(db_session, routine) == numbered("Day A", "Day C")
    assert db_session.get(WorkoutExercise, entry_id) is None
    assert db_session.scalar(select(func.count()).select_from(Set)) == 0
    assert db_session.get(Exercise, exercise_id) is not None


# Workouts: reordering all at once


def test_reordering_all_workouts(
    logged_in_client: TestClient, db_session: Session, routine: Routine
) -> None:
    a, b, c = make_workouts(db_session, routine, "A", "B", "C")
    ids = [str(workout.id) for workout in (c, a, b)]

    response = logged_in_client.put(
        f"/api/routines/{routine.id}/workouts/order", json={"workout_ids": ids}
    )

    assert response.status_code == 200, response.text
    assert [(w["name"], w["position"]) for w in response.json()] == numbered("C", "A", "B")
    assert workout_order(db_session, routine) == numbered("C", "A", "B")


def test_reordering_can_swap_two_workouts(
    logged_in_client: TestClient, db_session: Session, routine: Routine
) -> None:
    a, b = make_workouts(db_session, routine, "A", "B")

    response = logged_in_client.put(
        f"/api/routines/{routine.id}/workouts/order",
        json={"workout_ids": [str(b.id), str(a.id)]},
    )

    assert response.status_code == 200, response.text
    assert workout_order(db_session, routine) == numbered("B", "A")


def test_a_reorder_must_list_each_workout_exactly_once(
    logged_in_client: TestClient, db_session: Session, routine: Routine
) -> None:
    a, b = make_workouts(db_session, routine, "A", "B")
    (elsewhere,) = make_workouts(db_session, create_routine(db_session), "Other")
    path = f"/api/routines/{routine.id}/workouts/order"

    for ids in [[a.id], [a.id, b.id, elsewhere.id], [a.id, a.id], [b.id, elsewhere.id], []]:
        response = logged_in_client.put(path, json={"workout_ids": [str(id) for id in ids]})
        assert_error(response, 422, "invalid")
    assert workout_order(db_session, routine) == numbered("A", "B")


# Workouts: library and other users' routines are protected


def test_library_routine_workouts_cant_be_changed(
    logged_in_client: TestClient, db_session: Session
) -> None:
    library = create_routine(db_session)
    (workout,) = make_workouts(db_session, library, "Day A")
    reorder = {"workout_ids": [str(workout.id)]}

    responses = [
        logged_in_client.post(f"/api/routines/{library.id}/workouts", json={"name": "New"}),
        logged_in_client.put(f"/api/routines/{library.id}/workouts/order", json=reorder),
        logged_in_client.patch(f"/api/workouts/{workout.id}", json={"name": "Renamed"}),
        logged_in_client.delete(f"/api/workouts/{workout.id}"),
    ]

    for response in responses:
        assert_error(response, 403, "read_only")
    assert workout_order(db_session, library) == numbered("Day A")


def test_another_users_routine_workouts_cant_be_changed(
    logged_in_client: TestClient, db_session: Session
) -> None:
    theirs = create_routine(db_session, owner=create_user(db_session))
    (workout,) = make_workouts(db_session, theirs, "Day A")
    reorder = {"workout_ids": [str(workout.id)]}

    responses = [
        logged_in_client.post(f"/api/routines/{theirs.id}/workouts", json={"name": "New"}),
        logged_in_client.put(f"/api/routines/{theirs.id}/workouts/order", json=reorder),
        logged_in_client.patch(f"/api/workouts/{workout.id}", json={"name": "Renamed"}),
        logged_in_client.delete(f"/api/workouts/{workout.id}"),
    ]

    for response in responses:
        assert_error(response, 404, "not_found")
    assert workout_order(db_session, theirs) == numbered("Day A")


# Workout exercises


@pytest.fixture
def workout(db_session: Session, routine: Routine) -> Workout:
    return create_workout(db_session, routine, name="Day A")


def add(db_session: Session, workout: Workout, *names: str) -> list[WorkoutExercise]:
    return [
        create_workout_exercise(db_session, workout, create_exercise(db_session, name=name))
        for name in names
    ]


def test_listing_a_workouts_exercises_in_order(
    logged_in_client: TestClient, db_session: Session, workout: Workout
) -> None:
    squat = create_exercise(db_session, name="Squat")
    create_workout_exercise(
        db_session, workout, create_exercise(db_session, name="Row"), position=1
    )
    create_workout_exercise(db_session, workout, squat, position=0)

    body = logged_in_client.get(f"/api/workouts/{workout.id}/workout-exercises").json()

    assert [entry["exercise"]["name"] for entry in body["items"]] == ["Squat", "Row"]
    assert body["items"][0]["exercise"] == {
        "id": str(squat.id),
        "name": "Squat",
        "type": "strength",
    }
    assert body["items"][0]["workout_id"] == str(workout.id)


def test_adding_library_and_own_exercises(
    logged_in_client: TestClient, db_session: Session, workout: Workout, current_user: User
) -> None:
    add(db_session, workout, "Squat")
    library = create_exercise(db_session, name="Bench Press")
    own = create_exercise(db_session, name="My Row", owner=current_user)
    path = f"/api/workouts/{workout.id}/workout-exercises"

    appended = logged_in_client.post(path, json={"exercise_id": str(own.id)})
    inserted = logged_in_client.post(path, json={"exercise_id": str(library.id), "position": 0})

    assert appended.status_code == 201, appended.text
    assert appended.json()["exercise"]["name"] == "My Row"
    assert (appended.json()["position"], inserted.json()["position"]) == (1, 0)
    assert exercise_order(db_session, workout) == numbered("Bench Press", "Squat", "My Row")


def test_only_visible_exercises_can_be_added(
    logged_in_client: TestClient, db_session: Session, workout: Workout
) -> None:
    theirs = create_exercise(db_session, owner=create_user(db_session))
    path = f"/api/workouts/{workout.id}/workout-exercises"

    for exercise_id in [theirs.id, uuid.uuid4()]:
        response = logged_in_client.post(path, json={"exercise_id": str(exercise_id)})
        assert_error(response, 422, "invalid")
    assert exercise_order(db_session, workout) == []


def test_the_same_exercise_can_be_in_several_workouts(
    logged_in_client: TestClient, db_session: Session, routine: Routine, workout: Workout
) -> None:
    day_b = create_workout(db_session, routine, name="Day B")
    squat = create_exercise(db_session, name="Squat")
    body = {"exercise_id": str(squat.id)}

    for target in [workout, day_b, day_b]:
        response = logged_in_client.post(f"/api/workouts/{target.id}/workout-exercises", json=body)
        assert response.status_code == 201, response.text

    assert exercise_order(db_session, workout) == numbered("Squat")
    assert exercise_order(db_session, day_b) == numbered("Squat", "Squat")


def test_swapping_in_a_different_exercise_keeps_the_sets(
    logged_in_client: TestClient, db_session: Session, workout: Workout
) -> None:
    (entry,) = add(db_session, workout, "Squat")
    create_set(db_session, entry)
    front_squat = create_exercise(db_session, name="Front Squat")

    response = logged_in_client.patch(
        f"/api/workout-exercises/{entry.id}", json={"exercise_id": str(front_squat.id)}
    )

    assert response.status_code == 200, response.text
    assert response.json()["exercise"]["name"] == "Front Squat"
    assert exercise_order(db_session, workout) == numbered("Front Squat")
    assert db_session.scalar(select(func.count()).select_from(Set)) == 1


def test_swapping_in_an_invisible_exercise_is_rejected(
    logged_in_client: TestClient, db_session: Session, workout: Workout
) -> None:
    (entry,) = add(db_session, workout, "Squat")
    theirs = create_exercise(db_session, owner=create_user(db_session))

    response = logged_in_client.patch(
        f"/api/workout-exercises/{entry.id}", json={"exercise_id": str(theirs.id)}
    )

    assert_error(response, 422, "invalid")
    assert exercise_order(db_session, workout) == numbered("Squat")


def test_moving_an_exercise_forwards_and_backwards(
    logged_in_client: TestClient, db_session: Session, workout: Workout
) -> None:
    a, _, c = add(db_session, workout, "A", "B", "C")

    logged_in_client.patch(f"/api/workout-exercises/{a.id}", json={"position": 1})
    assert exercise_order(db_session, workout) == numbered("B", "A", "C")

    response = logged_in_client.patch(f"/api/workout-exercises/{c.id}", json={"position": 0})
    assert response.json()["position"] == 0
    assert exercise_order(db_session, workout) == numbered("C", "B", "A")


def test_deleting_a_workout_exercise_closes_the_gap_and_removes_its_sets(
    logged_in_client: TestClient, db_session: Session, workout: Workout
) -> None:
    _, b, _ = add(db_session, workout, "A", "B", "C")
    create_set(db_session, b)

    response = logged_in_client.delete(f"/api/workout-exercises/{b.id}")

    assert response.status_code == 204, response.text
    assert exercise_order(db_session, workout) == numbered("A", "C")
    assert db_session.scalar(select(func.count()).select_from(Set)) == 0


def test_reordering_and_swapping_a_workouts_exercises(
    logged_in_client: TestClient, db_session: Session, workout: Workout
) -> None:
    a, b, c = add(db_session, workout, "A", "B", "C")
    path = f"/api/workouts/{workout.id}/workout-exercises/order"

    response = logged_in_client.put(
        path, json={"workout_exercise_ids": [str(c.id), str(b.id), str(a.id)]}
    )

    assert response.status_code == 200, response.text
    assert [entry["exercise"]["name"] for entry in response.json()] == ["C", "B", "A"]
    assert exercise_order(db_session, workout) == numbered("C", "B", "A")


def test_a_workout_exercise_reorder_must_list_each_exactly_once(
    logged_in_client: TestClient, db_session: Session, routine: Routine, workout: Workout
) -> None:
    a, b = add(db_session, workout, "A", "B")
    (elsewhere,) = add(db_session, create_workout(db_session, routine), "Other")
    path = f"/api/workouts/{workout.id}/workout-exercises/order"

    for ids in [[a.id], [a.id, b.id, elsewhere.id], [b.id, b.id]]:
        response = logged_in_client.put(
            path, json={"workout_exercise_ids": [str(id) for id in ids]}
        )
        assert_error(response, 422, "invalid")
    assert exercise_order(db_session, workout) == numbered("A", "B")


def test_library_and_other_users_workout_exercises_are_protected(
    logged_in_client: TestClient, db_session: Session
) -> None:
    squat = create_exercise(db_session, name="Squat")
    for routine, status_code, code in [
        (create_routine(db_session), 403, "read_only"),
        (create_routine(db_session, owner=create_user(db_session)), 404, "not_found"),
    ]:
        workout = create_workout(db_session, routine)
        (entry,) = add(db_session, workout, f"Row {code}")
        nested = f"/api/workouts/{workout.id}/workout-exercises"
        responses = [
            logged_in_client.post(nested, json={"exercise_id": str(squat.id)}),
            logged_in_client.put(f"{nested}/order", json={"workout_exercise_ids": [str(entry.id)]}),
            logged_in_client.patch(f"/api/workout-exercises/{entry.id}", json={"position": 0}),
            logged_in_client.delete(f"/api/workout-exercises/{entry.id}"),
        ]

        for response in responses:
            assert_error(response, status_code, code)
        assert exercise_order(db_session, workout) == numbered(f"Row {code}")

    # Reading a library routine's workout exercises is fine
    library_entry = add(db_session, create_workout(db_session, create_routine(db_session)), "Dip")
    assert logged_in_client.get(f"/api/workout-exercises/{library_entry[0].id}").status_code == 200


def test_workouts_need_a_login(client: TestClient, db_session: Session) -> None:
    routine = create_routine(db_session)

    assert_error(client.get(f"/api/routines/{routine.id}/workouts"), 401, "not_authenticated")
