"""The sets of an exercise in a workout: defaults, validation, ordering and ownership"""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.common import WeightUnit
from app.models.set import Set
from app.models.user import User
from app.models.workout import WorkoutExercise
from tests.factories import (
    create_routine,
    create_set,
    create_user,
    create_workout,
    create_workout_exercise,
)
from tests.helpers import assert_error


@pytest.fixture
def entry(db_session: Session, current_user: User) -> WorkoutExercise:
    """An exercise in a workout of the current user's routine"""
    routine = create_routine(db_session, owner=current_user)
    return create_workout_exercise(db_session, create_workout(db_session, routine))


def make_sets(db_session: Session, entry: WorkoutExercise, *reps: int) -> list[Set]:
    return [create_set(db_session, entry, target_reps=count) for count in reps]


def stored_reps(db_session: Session, entry: WorkoutExercise) -> list[tuple[int, int]]:
    """(target_reps, position) of the sets, as stored"""
    db_session.expire_all()
    statement = (
        select(Set.target_reps, Set.position)
        .where(Set.workout_exercise_id == entry.id)
        .order_by(Set.position)
    )
    return [tuple(row) for row in db_session.execute(statement)]


def numbered(*reps: int) -> list[tuple[int, int]]:
    return [(count, position) for position, count in enumerate(reps)]


def sets_path(entry: WorkoutExercise) -> str:
    return f"/api/workout-exercises/{entry.id}/sets"


# Reading


def test_listing_sets_in_order(
    logged_in_client: TestClient, db_session: Session, entry: WorkoutExercise
) -> None:
    create_set(db_session, entry, position=1, target_reps=3)
    create_set(db_session, entry, position=0, target_reps=5, target_weight=Decimal("102.5"))

    body = logged_in_client.get(sets_path(entry)).json()

    assert [(s["target_reps"], s["position"]) for s in body["items"]] == numbered(5, 3)
    assert body["items"][0]["target_weight"] == "102.50"
    assert body["items"][0]["weight_unit"] == "kg"
    assert body["items"][0]["workout_exercise_id"] == str(entry.id)
    assert body["total"] == 2


def test_library_routines_sets_can_be_read(
    logged_in_client: TestClient, db_session: Session
) -> None:
    library_entry = create_workout_exercise(db_session)
    (set_,) = make_sets(db_session, library_entry, 5)

    assert logged_in_client.get(sets_path(library_entry)).json()["total"] == 1
    assert logged_in_client.get(f"/api/sets/{set_.id}").json()["target_reps"] == 5


def test_another_users_sets_are_not_found(
    logged_in_client: TestClient, db_session: Session
) -> None:
    routine = create_routine(db_session, owner=create_user(db_session))
    theirs = create_workout_exercise(db_session, create_workout(db_session, routine))
    (set_,) = make_sets(db_session, theirs, 5)

    assert_error(logged_in_client.get(sets_path(theirs)), 404, "not_found")
    assert_error(logged_in_client.get(f"/api/sets/{set_.id}"), 404, "not_found")
    assert_error(logged_in_client.get(f"/api/sets/{uuid.uuid4()}"), 404, "not_found")


# The new-set form


def test_new_copies_the_last_sets_targets(
    logged_in_client: TestClient, db_session: Session, entry: WorkoutExercise
) -> None:
    create_set(db_session, entry, position=1, target_reps=3, target_weight=Decimal("110"))
    create_set(
        db_session,
        entry,
        position=0,
        target_reps=5,
        target_weight=Decimal("100"),
        weight_unit=WeightUnit.LB,
    )

    response = logged_in_client.get(f"{sets_path(entry)}/new")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "defaults": {"target_reps": 3, "target_weight": "110.00", "weight_unit": "kg"},
        "options": {"weight_unit": ["kg", "lb"]},
    }


def test_new_for_the_first_set_offers_the_preferred_unit(
    logged_in_client: TestClient,
    db_session: Session,
    current_user: User,
    entry: WorkoutExercise,
) -> None:
    current_user.weight_unit = WeightUnit.LB
    db_session.flush()

    defaults = logged_in_client.get(f"{sets_path(entry)}/new").json()["defaults"]

    assert defaults == {"target_reps": None, "target_weight": None, "weight_unit": "lb"}


# Create


def test_creating_a_set_uses_the_preferred_unit(
    logged_in_client: TestClient,
    db_session: Session,
    current_user: User,
    entry: WorkoutExercise,
) -> None:
    current_user.weight_unit = WeightUnit.LB
    db_session.flush()

    response = logged_in_client.post(
        sets_path(entry), json={"target_reps": 5, "target_weight": 135}
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["target_reps"], body["target_weight"], body["weight_unit"]) == (5, "135.00", "lb")
    assert body["position"] == 0


def test_creating_appends_or_inserts_a_set(
    logged_in_client: TestClient, db_session: Session, entry: WorkoutExercise
) -> None:
    make_sets(db_session, entry, 5, 3)

    appended = logged_in_client.post(
        sets_path(entry), json={"target_reps": 1, "target_weight": "120", "weight_unit": "kg"}
    )
    inserted = logged_in_client.post(
        sets_path(entry), json={"target_reps": 8, "target_weight": "60", "position": 0}
    )

    assert (appended.json()["position"], inserted.json()["position"]) == (2, 0)
    assert stored_reps(db_session, entry) == numbered(8, 5, 3, 1)


@pytest.mark.parametrize(
    "change",
    [
        {"target_reps": 0},
        {"target_reps": -1},
        {"target_reps": 1001},
        {"target_weight": "-0.5"},
        {"target_weight": "60.125"},
        {"target_weight": "10000"},
        {"weight_unit": "stone"},
        {"position": -1},
        {"target_reps": None},
    ],
)
def test_invalid_sets_are_rejected(
    logged_in_client: TestClient, db_session: Session, entry: WorkoutExercise, change: dict
) -> None:
    body = {"target_reps": 5, "target_weight": "60"} | change

    assert_error(logged_in_client.post(sets_path(entry), json=body), 422, "invalid")
    assert stored_reps(db_session, entry) == []


def test_a_zero_weight_set_is_allowed(logged_in_client: TestClient, entry: WorkoutExercise) -> None:
    response = logged_in_client.post(sets_path(entry), json={"target_reps": 10, "target_weight": 0})

    assert response.status_code == 201, response.text
    assert response.json()["target_weight"] == "0.00"


# Update, move and delete


def test_updating_a_set(
    logged_in_client: TestClient, db_session: Session, entry: WorkoutExercise
) -> None:
    (set_,) = make_sets(db_session, entry, 5)

    response = logged_in_client.patch(
        f"/api/sets/{set_.id}", json={"target_weight": "62.5", "weight_unit": "lb"}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["target_reps"], body["target_weight"], body["weight_unit"]) == (5, "62.50", "lb")


@pytest.mark.parametrize(
    "change", [{"target_reps": 0}, {"target_weight": None}, {"weight_unit": None}]
)
def test_invalid_set_updates_are_rejected(
    logged_in_client: TestClient, db_session: Session, entry: WorkoutExercise, change: dict
) -> None:
    (set_,) = make_sets(db_session, entry, 5)

    assert_error(logged_in_client.patch(f"/api/sets/{set_.id}", json=change), 422, "invalid")


def test_moving_a_set_forwards_and_backwards(
    logged_in_client: TestClient, db_session: Session, entry: WorkoutExercise
) -> None:
    first, _, _, last = make_sets(db_session, entry, 1, 2, 3, 4)

    forwards = logged_in_client.patch(f"/api/sets/{first.id}", json={"position": 2})
    assert forwards.json()["position"] == 2
    assert stored_reps(db_session, entry) == numbered(2, 3, 1, 4)

    backwards = logged_in_client.patch(f"/api/sets/{last.id}", json={"position": 0})
    assert backwards.json()["position"] == 0
    assert stored_reps(db_session, entry) == numbered(4, 2, 3, 1)


def test_reordering_all_sets(
    logged_in_client: TestClient, db_session: Session, entry: WorkoutExercise
) -> None:
    a, b, c = make_sets(db_session, entry, 1, 2, 3)

    response = logged_in_client.put(
        f"{sets_path(entry)}/order", json={"set_ids": [str(c.id), str(a.id), str(b.id)]}
    )

    assert response.status_code == 200, response.text
    assert [s["target_reps"] for s in response.json()] == [3, 1, 2]
    assert stored_reps(db_session, entry) == numbered(3, 1, 2)


def test_reordering_can_swap_two_sets(
    logged_in_client: TestClient, db_session: Session, entry: WorkoutExercise
) -> None:
    a, b = make_sets(db_session, entry, 1, 2)

    response = logged_in_client.put(
        f"{sets_path(entry)}/order", json={"set_ids": [str(b.id), str(a.id)]}
    )

    assert response.status_code == 200, response.text
    assert stored_reps(db_session, entry) == numbered(2, 1)


def test_a_set_reorder_must_list_each_set_exactly_once(
    logged_in_client: TestClient, db_session: Session, entry: WorkoutExercise
) -> None:
    a, b = make_sets(db_session, entry, 1, 2)
    (elsewhere,) = make_sets(db_session, create_workout_exercise(db_session), 9)

    for ids in [[a.id], [a.id, b.id, elsewhere.id], [b.id, b.id], [b.id, elsewhere.id]]:
        response = logged_in_client.put(
            f"{sets_path(entry)}/order", json={"set_ids": [str(id) for id in ids]}
        )
        assert_error(response, 422, "invalid")
    assert stored_reps(db_session, entry) == numbered(1, 2)


def test_deleting_a_set_closes_the_gap(
    logged_in_client: TestClient, db_session: Session, entry: WorkoutExercise
) -> None:
    _, middle, _ = make_sets(db_session, entry, 1, 2, 3)

    response = logged_in_client.delete(f"/api/sets/{middle.id}")

    assert response.status_code == 204, response.text
    assert stored_reps(db_session, entry) == numbered(1, 3)


# Library and other users' routines are protected


@pytest.mark.parametrize(
    ("owner", "status_code", "code"),
    [("library", 403, "read_only"), ("someone else", 404, "not_found")],
)
def test_sets_of_routines_that_arent_yours_cant_be_changed(
    logged_in_client: TestClient, db_session: Session, owner: str, status_code: int, code: str
) -> None:
    user = None if owner == "library" else create_user(db_session)
    routine = create_routine(db_session, owner=user)
    theirs = create_workout_exercise(db_session, create_workout(db_session, routine))
    (set_,) = make_sets(db_session, theirs, 5)

    responses = [
        logged_in_client.get(f"{sets_path(theirs)}/new"),
        logged_in_client.post(sets_path(theirs), json={"target_reps": 5, "target_weight": 60}),
        logged_in_client.put(f"{sets_path(theirs)}/order", json={"set_ids": [str(set_.id)]}),
        logged_in_client.patch(f"/api/sets/{set_.id}", json={"target_reps": 1}),
        logged_in_client.delete(f"/api/sets/{set_.id}"),
    ]

    for response in responses:
        assert_error(response, status_code, code)
    assert stored_reps(db_session, theirs) == numbered(5)


def test_sets_need_a_login(client: TestClient, entry: WorkoutExercise) -> None:
    assert_error(client.get(sets_path(entry)), 401, "not_authenticated")
