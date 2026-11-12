"""A routine's cycle through the API: slots that say which of its workouts comes when"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.routine import Routine
from app.models.routine_workout import RoutineWorkout
from app.models.user import User
from app.models.workout import Workout
from tests.factories import create_routine, create_routine_workout, create_user, create_workout
from tests.helpers import assert_error


@pytest.fixture
def routine(db_session: Session, current_user: User) -> Routine:
    return create_routine(db_session, owner=current_user)


@pytest.fixture
def day_a(db_session: Session, routine: Routine) -> Workout:
    return create_workout(db_session, routine, name="Day A")


@pytest.fixture
def day_b(db_session: Session, routine: Routine) -> Workout:
    return create_workout(db_session, routine, name="Day B")


def cycle(db_session: Session, routine: Routine) -> list[tuple[str, int]]:
    """(workout name, position) of the routine's slots, as stored"""
    db_session.expire_all()
    statement = (
        select(Workout.name, RoutineWorkout.position)
        .join(RoutineWorkout.workout)
        .where(RoutineWorkout.routine_id == routine.id)
        .order_by(RoutineWorkout.position)
    )
    return [tuple(row) for row in db_session.execute(statement)]


def numbered(*names: str) -> list[tuple[str, int]]:
    return [(name, position) for position, name in enumerate(names)]


def slots_path(routine: Routine) -> str:
    return f"/api/routines/{routine.id}/routine-workouts"


# Reading


def test_listing_the_cycle_in_position_order(
    logged_in_client: TestClient, db_session: Session, routine: Routine, day_a: Workout
) -> None:
    day_b = create_workout(db_session, routine, name="Day B")
    create_routine_workout(db_session, day_a, position=2)
    create_routine_workout(db_session, day_b, position=1)
    create_routine_workout(db_session, day_a, position=0)

    body = logged_in_client.get(slots_path(routine)).json()

    assert [(slot["workout"]["name"], slot["position"]) for slot in body["items"]] == numbered(
        "Day A", "Day B", "Day A"
    )
    assert body["items"][0]["workout"] == {"id": str(day_a.id), "name": "Day A"}
    assert body["items"][0]["routine_id"] == str(routine.id)
    assert body["total"] == 3


def test_a_library_routines_cycle_can_be_read(
    logged_in_client: TestClient, db_session: Session
) -> None:
    slot = create_routine_workout(db_session, create_workout(db_session, name="Day A"))

    listed = logged_in_client.get(slots_path(slot.routine))
    shown = logged_in_client.get(f"/api/routine-workouts/{slot.id}")

    assert listed.json()["total"] == 1
    assert shown.status_code == 200
    assert shown.json()["workout"]["name"] == "Day A"


def test_another_users_cycle_is_not_found(
    logged_in_client: TestClient, db_session: Session
) -> None:
    theirs = create_routine(db_session, owner=create_user(db_session))
    slot = create_routine_workout(db_session, create_workout(db_session, theirs))

    assert_error(logged_in_client.get(slots_path(theirs)), 404, "not_found")
    assert_error(logged_in_client.get(f"/api/routine-workouts/{slot.id}"), 404, "not_found")
    assert_error(logged_in_client.get(f"/api/routine-workouts/{uuid.uuid4()}"), 404, "not_found")


# Adding slots


def test_adding_slots_appends_inserts_and_can_repeat_a_workout(
    logged_in_client: TestClient,
    db_session: Session,
    routine: Routine,
    day_a: Workout,
    day_b: Workout,
) -> None:
    path = slots_path(routine)

    first = logged_in_client.post(path, json={"workout_id": str(day_a.id)})
    again = logged_in_client.post(path, json={"workout_id": str(day_a.id)})
    middle = logged_in_client.post(path, json={"workout_id": str(day_b.id), "position": 1})
    past_end = logged_in_client.post(path, json={"workout_id": str(day_b.id), "position": 99})

    assert first.status_code == 201, first.text
    assert first.json()["workout"] == {"id": str(day_a.id), "name": "Day A"}
    assert [r.json()["position"] for r in (first, again, middle, past_end)] == [0, 1, 1, 3]
    assert cycle(db_session, routine) == numbered("Day A", "Day B", "Day A", "Day B")


def test_a_slot_must_point_at_one_of_the_routines_workouts(
    logged_in_client: TestClient, db_session: Session, routine: Routine
) -> None:
    elsewhere = create_workout(db_session, create_routine(db_session))

    for workout_id in [elsewhere.id, uuid.uuid4()]:
        response = logged_in_client.post(slots_path(routine), json={"workout_id": str(workout_id)})
        assert_error(response, 422, "invalid")
    assert cycle(db_session, routine) == []


@pytest.mark.parametrize("body", [{}, {"position": 0}, {"workout_id": "x"}])
def test_invalid_slots_are_rejected(
    logged_in_client: TestClient, routine: Routine, body: dict
) -> None:
    assert_error(logged_in_client.post(slots_path(routine), json=body), 422, "invalid")


def test_a_negative_position_is_rejected(
    logged_in_client: TestClient, routine: Routine, day_a: Workout
) -> None:
    body = {"workout_id": str(day_a.id), "position": -1}

    assert_error(logged_in_client.post(slots_path(routine), json=body), 422, "invalid")


# Changing slots


def test_swapping_the_workout_in_a_slot(
    logged_in_client: TestClient,
    db_session: Session,
    routine: Routine,
    day_a: Workout,
    day_b: Workout,
) -> None:
    create_routine_workout(db_session, day_a)
    slot = create_routine_workout(db_session, day_a)

    response = logged_in_client.patch(
        f"/api/routine-workouts/{slot.id}", json={"workout_id": str(day_b.id)}
    )

    assert response.status_code == 200, response.text
    assert response.json()["workout"]["name"] == "Day B"
    assert cycle(db_session, routine) == numbered("Day A", "Day B")


def test_swapping_in_another_routines_workout_is_rejected(
    logged_in_client: TestClient, db_session: Session, routine: Routine, day_a: Workout
) -> None:
    slot = create_routine_workout(db_session, day_a)
    elsewhere = create_workout(db_session, create_routine(db_session))

    response = logged_in_client.patch(
        f"/api/routine-workouts/{slot.id}", json={"workout_id": str(elsewhere.id)}
    )

    assert_error(response, 422, "invalid")
    assert cycle(db_session, routine) == numbered("Day A")


def test_moving_a_slot_forwards_and_backwards(
    logged_in_client: TestClient, db_session: Session, routine: Routine
) -> None:
    a, _, _, d = [
        create_routine_workout(db_session, create_workout(db_session, routine, name=name))
        for name in "ABCD"
    ]

    forwards = logged_in_client.patch(f"/api/routine-workouts/{a.id}", json={"position": 2})
    assert forwards.json()["position"] == 2
    assert cycle(db_session, routine) == numbered("B", "C", "A", "D")

    backwards = logged_in_client.patch(f"/api/routine-workouts/{d.id}", json={"position": 0})
    assert backwards.json()["position"] == 0
    assert cycle(db_session, routine) == numbered("D", "B", "C", "A")


def test_removing_a_slot_closes_the_gap_and_keeps_the_workout(
    logged_in_client: TestClient,
    db_session: Session,
    routine: Routine,
    day_a: Workout,
    day_b: Workout,
) -> None:
    create_routine_workout(db_session, day_a)
    middle = create_routine_workout(db_session, day_b)
    create_routine_workout(db_session, day_a)

    response = logged_in_client.delete(f"/api/routine-workouts/{middle.id}")

    assert response.status_code == 204, response.text
    assert cycle(db_session, routine) == numbered("Day A", "Day A")
    assert db_session.get(Workout, day_b.id) is not None


# Reordering the whole cycle


def test_reordering_and_swapping_slots(
    logged_in_client: TestClient,
    db_session: Session,
    routine: Routine,
    day_a: Workout,
    day_b: Workout,
) -> None:
    a = create_routine_workout(db_session, day_a)
    b = create_routine_workout(db_session, day_b)
    c = create_routine_workout(db_session, day_a)

    response = logged_in_client.put(
        f"{slots_path(routine)}/order",
        json={"routine_workout_ids": [str(b.id), str(c.id), str(a.id)]},
    )

    assert response.status_code == 200, response.text
    assert [slot["id"] for slot in response.json()] == [str(b.id), str(c.id), str(a.id)]
    assert cycle(db_session, routine) == numbered("Day B", "Day A", "Day A")


def test_a_reorder_must_list_each_slot_exactly_once(
    logged_in_client: TestClient,
    db_session: Session,
    routine: Routine,
    day_a: Workout,
    day_b: Workout,
) -> None:
    a = create_routine_workout(db_session, day_a)
    b = create_routine_workout(db_session, day_b)
    elsewhere = create_routine_workout(db_session)

    for ids in [[a.id], [a.id, b.id, elsewhere.id], [b.id, b.id], [b.id, elsewhere.id], []]:
        response = logged_in_client.put(
            f"{slots_path(routine)}/order", json={"routine_workout_ids": [str(id) for id in ids]}
        )
        assert_error(response, 422, "invalid")
    assert cycle(db_session, routine) == numbered("Day A", "Day B")


# Library and other users' routines are protected


@pytest.mark.parametrize(
    ("owner", "status_code", "code"),
    [("library", 403, "read_only"), ("someone else", 404, "not_found")],
)
def test_cycles_of_routines_that_arent_yours_cant_be_changed(
    logged_in_client: TestClient, db_session: Session, owner: str, status_code: int, code: str
) -> None:
    user = None if owner == "library" else create_user(db_session)
    routine = create_routine(db_session, owner=user)
    workout = create_workout(db_session, routine, name="Day A")
    slot = create_routine_workout(db_session, workout)
    path = f"/api/routine-workouts/{slot.id}"

    responses = [
        logged_in_client.post(slots_path(routine), json={"workout_id": str(workout.id)}),
        logged_in_client.put(
            f"{slots_path(routine)}/order", json={"routine_workout_ids": [str(slot.id)]}
        ),
        logged_in_client.patch(path, json={"position": 0}),
        logged_in_client.delete(path),
    ]

    for response in responses:
        assert_error(response, status_code, code)
    assert cycle(db_session, routine) == numbered("Day A")


def test_the_cycle_needs_a_login(client: TestClient, routine: Routine) -> None:
    assert_error(client.get(slots_path(routine)), 401, "not_authenticated")
