"""Copying a routine with all its contents"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.common import WeightUnit
from app.models.exercise import Exercise
from app.models.routine import Routine
from app.models.user import User
from tests.factories import (
    create_exercise,
    create_routine,
    create_routine_workout,
    create_set,
    create_user,
    create_workout,
    create_workout_exercise,
)
from tests.helpers import assert_error


def build_source(db_session: Session, owner: User | None = None) -> Routine:
    """Two workouts of two exercises with two sets each, in a cycle that repeats one: A, B, A.
    Workouts are added B first; the other levels are created out of order (later positions
    first) so copying in creation order would show"""
    routine = create_routine(
        db_session, name="Starting Strength", description="Three days a week", owner=owner
    )
    squat = create_exercise(db_session, name=f"Squat {uuid.uuid4().hex[:6]}")
    press = create_exercise(db_session, name=f"Press {uuid.uuid4().hex[:6]}")
    added = datetime(2026, 1, 1, tzinfo=UTC)
    workouts = {}
    for offset, name in [(1, "Day B"), (0, "Day A")]:
        workout = create_workout(
            db_session, routine, name=name, created_at=added + timedelta(days=offset)
        )
        workouts[name] = workout
        for entry_position, exercise in [(1, press), (0, squat)]:
            entry = create_workout_exercise(db_session, workout, exercise, position=entry_position)
            for set_position, reps in [(1, 3), (0, 5)]:
                create_set(
                    db_session,
                    entry,
                    position=set_position,
                    target_reps=reps,
                    target_weight=Decimal("60") + offset * 10 + set_position,
                    weight_unit=WeightUnit.LB if entry_position else WeightUnit.KG,
                )
    for position, name in [(2, "Day A"), (1, "Day B"), (0, "Day A")]:
        create_routine_workout(db_session, workouts[name], position=position)
    return routine


def contents(detail: dict) -> dict:
    """A routine detail without ids, timestamps or ownership, to compare a copy's contents"""
    return {
        "workouts": [
            {
                "name": workout["name"],
                "exercises": [
                    {
                        "position": entry["position"],
                        "exercise": entry["exercise"],
                        "sets": [
                            {
                                key: set_[key]
                                for key in (
                                    "position",
                                    "target_reps",
                                    "target_weight",
                                    "weight_unit",
                                )
                            }
                            for set_ in entry["sets"]
                        ],
                    }
                    for entry in workout["exercises"]
                ],
            }
            for workout in detail["workouts"]
        ],
        # The cycle by workout name, since a copy's workouts have new ids
        "slots": [(slot["position"], slot["workout"]["name"]) for slot in detail["slots"]],
    }


def copy_path(routine: Routine) -> str:
    return f"/api/routines/{routine.id}/copy"


def test_copying_a_library_routine_copies_everything_in_order(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    source = build_source(db_session)
    original = logged_in_client.get(f"/api/routines/{source.id}").json()

    response = logged_in_client.post(copy_path(source), json={})

    assert response.status_code == 201, response.text
    body = response.json()
    assert contents(body) == contents(original)
    assert [w["name"] for w in body["workouts"]] == ["Day A", "Day B"]
    assert contents(body)["slots"] == [(0, "Day A"), (1, "Day B"), (2, "Day A")]
    # The copy's slots point at the copy's own workouts
    copied_ids = {workout["id"] for workout in body["workouts"]}
    assert {slot["workout"]["id"] for slot in body["slots"]} == copied_ids
    assert [s["target_reps"] for s in body["workouts"][0]["exercises"][0]["sets"]] == [5, 3]
    # New rows throughout, in a routine the user owns that links back to its source
    assert body["id"] != original["id"]
    assert body["workouts"][0]["id"] != original["workouts"][0]["id"]
    assert (body["name"], body["description"]) == ("Starting Strength", "Three days a week")
    assert body["is_library"] is False
    assert body["source_routine_id"] == str(source.id)
    copy = db_session.get(Routine, uuid.UUID(body["id"]))
    assert copy is not None and copy.owner_id == current_user.id


def test_exercises_are_referenced_not_copied(
    logged_in_client: TestClient, db_session: Session
) -> None:
    source = build_source(db_session)
    exercises_before = db_session.scalar(select(func.count()).select_from(Exercise))

    body = logged_in_client.post(copy_path(source), json={}).json()

    db_session.expire_all()
    assert db_session.scalar(select(func.count()).select_from(Exercise)) == exercises_before
    assert body["workouts"][0]["exercises"][0]["exercise"]["id"] in {
        str(exercise_id) for exercise_id in db_session.scalars(select(Exercise.id))
    }


def test_the_name_and_description_can_be_changed_or_cleared(
    logged_in_client: TestClient, db_session: Session
) -> None:
    source = build_source(db_session)

    renamed = logged_in_client.post(copy_path(source), json={"name": "  My 5x5  "}).json()
    cleared = logged_in_client.post(copy_path(source), json={"description": None}).json()

    assert (renamed["name"], renamed["description"]) == ("My 5x5", "Three days a week")
    assert (cleared["name"], cleared["description"]) == ("Starting Strength", None)


@pytest.mark.parametrize("body", [{"name": "  "}, {"name": "x" * 101}])
def test_an_invalid_copy_name_is_rejected(
    logged_in_client: TestClient, db_session: Session, body: dict
) -> None:
    source = build_source(db_session)

    assert_error(logged_in_client.post(copy_path(source), json=body), 422, "invalid")


def test_editing_the_copy_leaves_the_original_alone(
    logged_in_client: TestClient, db_session: Session
) -> None:
    source = build_source(db_session)
    before = logged_in_client.get(f"/api/routines/{source.id}").json()
    copy = logged_in_client.post(copy_path(source), json={}).json()
    first_workout = copy["workouts"][0]
    first_entry = first_workout["exercises"][0]

    edits = [
        logged_in_client.patch(f"/api/routines/{copy['id']}", json={"name": "Changed"}),
        logged_in_client.patch(f"/api/workouts/{first_workout['id']}", json={"name": "Legs"}),
        logged_in_client.delete(f"/api/workout-exercises/{first_entry['id']}"),
        logged_in_client.delete(f"/api/workouts/{copy['workouts'][1]['id']}"),
    ]

    assert [response.status_code for response in edits] == [200, 200, 204, 204]
    after = logged_in_client.get(f"/api/routines/{source.id}").json()
    assert contents(after) == contents(before)
    assert after["name"] == "Starting Strength"


def test_the_users_own_routine_can_be_copied(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    source = build_source(db_session, owner=current_user)

    response = logged_in_client.post(copy_path(source), json={"name": "Deload week"})

    assert response.status_code == 201, response.text
    assert response.json()["source_routine_id"] == str(source.id)
    assert len(response.json()["workouts"]) == 2


def test_an_empty_routine_can_be_copied(logged_in_client: TestClient, db_session: Session) -> None:
    source = create_routine(db_session, name="Blank")

    body = logged_in_client.post(copy_path(source), json={}).json()

    assert (body["name"], body["workouts"]) == ("Blank", [])
    assert "progressions" not in body


def test_another_users_routine_cant_be_copied(
    logged_in_client: TestClient, db_session: Session
) -> None:
    theirs = build_source(db_session, owner=create_user(db_session))
    routines_before = db_session.scalar(select(func.count()).select_from(Routine))

    assert_error(logged_in_client.post(copy_path(theirs), json={}), 404, "not_found")
    assert_error(
        logged_in_client.post(f"/api/routines/{uuid.uuid4()}/copy", json={}), 404, "not_found"
    )
    db_session.expire_all()
    assert db_session.scalar(select(func.count()).select_from(Routine)) == routines_before


def test_copying_needs_a_login(client: TestClient, db_session: Session) -> None:
    source = create_routine(db_session)

    assert_error(client.post(copy_path(source), json={}), 401, "not_authenticated")
