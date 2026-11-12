"""Logging sets into workout sessions with PUT, and reading them back by session and by
exercise"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.common import WeightUnit
from app.models.exercise import Exercise
from app.models.set import Set
from app.models.set_record import SetRecord
from app.models.user import User
from app.models.workout_session import WorkoutSession
from tests.factories import (
    create_exercise,
    create_routine,
    create_routine_workout,
    create_set,
    create_set_record,
    create_user,
    create_workout,
    create_workout_exercise,
    create_workout_session,
)
from tests.helpers import assert_error

DAY = datetime(2026, 11, 2, 18, 0, tzinfo=UTC)


@pytest.fixture
def squat(db_session: Session) -> Exercise:
    return create_exercise(db_session, name="Squat")


@pytest.fixture
def freestyle(db_session: Session, current_user: User) -> WorkoutSession:
    return create_workout_session(db_session, user=current_user, performed_at=DAY)


@pytest.fixture
def planned(
    db_session: Session, current_user: User, squat: Exercise
) -> tuple[WorkoutSession, list[Set]]:
    """A session done from a slot whose workout prescribes two squat sets"""
    routine = create_routine(db_session, owner=current_user)
    workout = create_workout(db_session, routine)
    entry = create_workout_exercise(db_session, workout, squat)
    sets = [
        create_set(db_session, entry, target_reps=5, target_weight=Decimal("100")),
        create_set(db_session, entry, target_reps=3, target_weight=Decimal("110")),
    ]
    slot = create_routine_workout(db_session, workout)
    session = create_workout_session(db_session, user=current_user, routine_workout=slot)
    return session, sets


def record_body(session: WorkoutSession, exercise: Exercise, **overrides: object) -> dict:
    fields = {
        "session_id": str(session.id),
        "exercise_id": str(exercise.id),
        "reps": 5,
        "weight": "100",
    }
    return fields | overrides


def put_record(
    client: TestClient, session: WorkoutSession, exercise: Exercise, **overrides: object
) -> dict:
    response = client.put(
        f"/api/set-records/{uuid.uuid4()}", json=record_body(session, exercise, **overrides)
    )
    assert response.status_code == 201, response.text
    return response.json()


def stored(db_session: Session, session: WorkoutSession) -> list[tuple[int, int]]:
    """(reps, position) of the session's records, as stored"""
    db_session.expire_all()
    statement = (
        select(SetRecord.reps, SetRecord.position)
        .where(SetRecord.session_id == session.id)
        .order_by(SetRecord.position)
    )
    return [tuple(row) for row in db_session.execute(statement)]


def numbered(*reps: int) -> list[tuple[int, int]]:
    return [(count, position) for position, count in enumerate(reps)]


def history_path(exercise: Exercise) -> str:
    return f"/api/exercises/{exercise.id}/set-records"


def session_records_path(session: WorkoutSession) -> str:
    return f"/api/workout-sessions/{session.id}/set-records"


# Logging with PUT


def test_put_creates_then_replaces_a_record(
    logged_in_client: TestClient, db_session: Session, freestyle: WorkoutSession, squat: Exercise
) -> None:
    path = f"/api/set-records/{uuid.uuid4()}"
    body = record_body(freestyle, squat)

    created = logged_in_client.put(path, json=body)
    replaced = logged_in_client.put(path, json=body | {"reps": 4, "weight": 102.5})
    retried = logged_in_client.put(path, json=body | {"reps": 4, "weight": 102.5})

    assert [r.status_code for r in (created, replaced, retried)] == [201, 200, 200]
    assert (replaced.json()["reps"], replaced.json()["weight"]) == (4, "102.50")
    assert replaced.json()["id"] == created.json()["id"]
    assert stored(db_session, freestyle) == numbered(4)


def test_a_record_takes_its_owner_and_time_from_the_session(
    logged_in_client: TestClient,
    db_session: Session,
    current_user: User,
    freestyle: WorkoutSession,
    squat: Exercise,
) -> None:
    current_user.weight_unit = WeightUnit.LB
    db_session.flush()

    body = put_record(logged_in_client, freestyle, squat)

    assert body["session_id"] == str(freestyle.id)
    assert datetime.fromisoformat(body["performed_at"]) == DAY
    assert body["weight_unit"] == "lb"
    assert (body["set_id"], body["target_reps"], body["target_unit"]) == (None, None, None)


def test_records_append_insert_and_keep_their_place(
    logged_in_client: TestClient, db_session: Session, freestyle: WorkoutSession, squat: Exercise
) -> None:
    first = put_record(logged_in_client, freestyle, squat, reps=1)
    put_record(logged_in_client, freestyle, squat, reps=2)
    put_record(logged_in_client, freestyle, squat, reps=9, position=0)
    assert stored(db_session, freestyle) == numbered(9, 1, 2)

    # Replacing without a position keeps the record where it is
    logged_in_client.put(
        f"/api/set-records/{first['id']}", json=record_body(freestyle, squat, reps=8)
    )
    assert stored(db_session, freestyle) == numbered(9, 8, 2)

    # With one, it moves
    logged_in_client.put(
        f"/api/set-records/{first['id']}", json=record_body(freestyle, squat, reps=8, position=2)
    )
    assert stored(db_session, freestyle) == numbered(9, 2, 8)


def test_a_record_can_move_to_another_session(
    logged_in_client: TestClient,
    db_session: Session,
    current_user: User,
    freestyle: WorkoutSession,
    squat: Exercise,
) -> None:
    other = create_workout_session(db_session, user=current_user)
    put_record(logged_in_client, freestyle, squat, reps=1)
    moving = put_record(logged_in_client, freestyle, squat, reps=2)
    put_record(logged_in_client, freestyle, squat, reps=3)

    response = logged_in_client.put(
        f"/api/set-records/{moving['id']}", json=record_body(other, squat, reps=2)
    )

    assert response.status_code == 200, response.text
    assert stored(db_session, freestyle) == numbered(1, 3)
    assert stored(db_session, other) == numbered(2)


def test_another_users_record_id_is_a_409(
    logged_in_client: TestClient, db_session: Session, freestyle: WorkoutSession, squat: Exercise
) -> None:
    theirs = create_set_record(db_session, user=create_user(db_session), exercise=squat, reps=8)

    response = logged_in_client.put(
        f"/api/set-records/{theirs.id}", json=record_body(freestyle, squat)
    )

    assert_error(response, 409, "id_conflict")
    db_session.expire_all()
    assert db_session.get(SetRecord, theirs.id).reps == 8


def test_another_users_or_an_unknown_session_is_not_found(
    logged_in_client: TestClient, db_session: Session, squat: Exercise
) -> None:
    theirs = create_workout_session(db_session, user=create_user(db_session))
    unknown = WorkoutSession(id=uuid.uuid4())

    for session in [theirs, unknown]:
        response = logged_in_client.put(
            f"/api/set-records/{uuid.uuid4()}", json=record_body(session, squat)
        )
        assert_error(response, 404, "not_found")
    assert stored(db_session, theirs) == []


def test_only_visible_exercises_can_be_logged(
    logged_in_client: TestClient, db_session: Session, freestyle: WorkoutSession
) -> None:
    theirs = create_exercise(db_session, owner=create_user(db_session))

    for exercise_id in [theirs.id, uuid.uuid4()]:
        response = logged_in_client.put(
            f"/api/set-records/{uuid.uuid4()}",
            json=record_body(freestyle, theirs, exercise_id=str(exercise_id)),
        )
        assert_error(response, 422, "invalid")
    assert stored(db_session, freestyle) == []


@pytest.mark.parametrize(
    "change",
    [
        {"reps": -1},
        {"reps": 1001},
        {"reps": None},
        {"weight": "-0.5"},
        {"weight": "100.125"},
        {"weight": "10000"},
        {"weight_unit": "stone"},
        {"position": -1},
        {"session_id": None},
    ],
)
def test_invalid_records_are_rejected(
    logged_in_client: TestClient,
    db_session: Session,
    freestyle: WorkoutSession,
    squat: Exercise,
    change: dict,
) -> None:
    response = logged_in_client.put(
        f"/api/set-records/{uuid.uuid4()}", json=record_body(freestyle, squat) | change
    )

    assert_error(response, 422, "invalid")
    assert stored(db_session, freestyle) == []


def test_a_failed_attempt_with_zero_reps_can_be_logged(
    logged_in_client: TestClient, freestyle: WorkoutSession, squat: Exercise
) -> None:
    assert put_record(logged_in_client, freestyle, squat, reps=0)["reps"] == 0


# Linking records to prescribed sets


def test_linking_a_set_copies_its_targets_once(
    logged_in_client: TestClient,
    db_session: Session,
    planned: tuple[WorkoutSession, list[Set]],
    squat: Exercise,
) -> None:
    session, (first, _) = planned
    path = f"/api/set-records/{uuid.uuid4()}"
    body = record_body(session, squat, set_id=str(first.id), reps=5, weight="100")
    # As a real request would, read the stored NUMERIC(6, 2) targets, not the factory's
    db_session.expire_all()

    linked = logged_in_client.put(path, json=body).json()
    first.target_weight = Decimal("105")
    db_session.flush()
    retried = logged_in_client.put(path, json=body).json()

    for record in [linked, retried]:
        assert record["set_id"] == str(first.id)
        assert (record["target_reps"], record["target_weight"], record["target_unit"]) == (
            5,
            "100.00",
            "kg",
        )


def test_unlinking_clears_the_targets(
    logged_in_client: TestClient,
    planned: tuple[WorkoutSession, list[Set]],
    squat: Exercise,
) -> None:
    session, (first, _) = planned
    path = f"/api/set-records/{uuid.uuid4()}"
    logged_in_client.put(path, json=record_body(session, squat, set_id=str(first.id)))

    body = logged_in_client.put(path, json=record_body(session, squat, set_id=None)).json()

    assert (body["set_id"], body["target_reps"], body["target_weight"]) == (None, None, None)


def test_a_session_holds_more_or_fewer_records_than_prescribed(
    logged_in_client: TestClient,
    db_session: Session,
    planned: tuple[WorkoutSession, list[Set]],
    squat: Exercise,
) -> None:
    session, (first, second) = planned
    put_record(logged_in_client, session, squat, set_id=str(first.id), reps=5)
    put_record(logged_in_client, session, squat, set_id=str(second.id), reps=3)
    put_record(logged_in_client, session, squat, reps=8, weight="80")

    assert stored(db_session, session) == numbered(5, 3, 8)


def test_a_set_from_another_workout_is_rejected(
    logged_in_client: TestClient,
    db_session: Session,
    planned: tuple[WorkoutSession, list[Set]],
    freestyle: WorkoutSession,
    squat: Exercise,
) -> None:
    session, (first, _) = planned
    elsewhere = create_set(db_session)

    for target, set_ in [(session, elsewhere), (freestyle, first)]:
        response = logged_in_client.put(
            f"/api/set-records/{uuid.uuid4()}",
            json=record_body(target, squat, set_id=str(set_.id)),
        )
        assert_error(response, 422, "invalid")
    assert stored(db_session, session) == []


# A session's records


def test_listing_a_sessions_records_in_order(
    logged_in_client: TestClient, freestyle: WorkoutSession, squat: Exercise
) -> None:
    for reps in [5, 3, 1]:
        put_record(logged_in_client, freestyle, squat, reps=reps)

    body = logged_in_client.get(session_records_path(freestyle)).json()

    assert [(item["reps"], item["position"]) for item in body["items"]] == numbered(5, 3, 1)
    assert body["total"] == 3


def test_reordering_a_sessions_records(
    logged_in_client: TestClient, db_session: Session, freestyle: WorkoutSession, squat: Exercise
) -> None:
    a, b, c = [put_record(logged_in_client, freestyle, squat, reps=reps) for reps in (1, 2, 3)]

    response = logged_in_client.put(
        f"{session_records_path(freestyle)}/order",
        json={"set_record_ids": [c["id"], a["id"], b["id"]]},
    )

    assert response.status_code == 200, response.text
    assert [item["reps"] for item in response.json()] == [3, 1, 2]
    assert stored(db_session, freestyle) == numbered(3, 1, 2)


def test_a_reorder_must_list_each_record_exactly_once(
    logged_in_client: TestClient, db_session: Session, freestyle: WorkoutSession, squat: Exercise
) -> None:
    a, b = [put_record(logged_in_client, freestyle, squat, reps=reps) for reps in (1, 2)]
    elsewhere = create_set_record(db_session)

    for ids in [[a["id"]], [a["id"], b["id"], str(elsewhere.id)], [b["id"], b["id"]], []]:
        response = logged_in_client.put(
            f"{session_records_path(freestyle)}/order", json={"set_record_ids": ids}
        )
        assert_error(response, 422, "invalid")
    assert stored(db_session, freestyle) == numbered(1, 2)


def test_deleting_a_record_closes_the_gap(
    logged_in_client: TestClient, db_session: Session, freestyle: WorkoutSession, squat: Exercise
) -> None:
    _, middle, _ = [put_record(logged_in_client, freestyle, squat, reps=reps) for reps in (1, 2, 3)]

    response = logged_in_client.delete(f"/api/set-records/{middle['id']}")

    assert response.status_code == 204, response.text
    assert stored(db_session, freestyle) == numbered(1, 3)


def test_another_users_records_are_not_found(
    logged_in_client: TestClient, db_session: Session
) -> None:
    theirs = create_set_record(db_session, user=create_user(db_session))
    path = f"/api/set-records/{theirs.id}"

    assert_error(logged_in_client.get(path), 404, "not_found")
    assert_error(logged_in_client.delete(path), 404, "not_found")
    assert_error(logged_in_client.get(session_records_path(theirs.session)), 404, "not_found")
    assert_error(
        logged_in_client.put(
            f"{session_records_path(theirs.session)}/order",
            json={"set_record_ids": [str(theirs.id)]},
        ),
        404,
        "not_found",
    )
    db_session.expire_all()
    assert db_session.scalar(select(func.count()).select_from(SetRecord)) == 1


# An exercise's history


def make_sessions(
    db_session: Session, user: User, exercise: Exercise, *reps_by_day: list[int]
) -> list[WorkoutSession]:
    """One session a day from DAY, each with records of `exercise` for the given reps"""
    sessions = []
    for day, reps in enumerate(reps_by_day):
        session = create_workout_session(db_session, user=user, performed_at=DAY + timedelta(day))
        for count in reps:
            create_set_record(db_session, session, exercise=exercise, reps=count)
        sessions.append(session)
    return sessions


def reps(body: dict) -> list[int]:
    return [item["reps"] for item in body["items"]]


def test_history_is_newest_session_first_then_in_order(
    logged_in_client: TestClient, db_session: Session, current_user: User, squat: Exercise
) -> None:
    make_sessions(db_session, current_user, squat, [5, 4], [3, 2], [1])
    create_set_record(db_session, user=create_user(db_session), exercise=squat, reps=99)
    create_set_record(db_session, user=current_user, reps=98)

    body = logged_in_client.get(history_path(squat)).json()

    assert reps(body) == [1, 3, 2, 5, 4]
    assert body["total"] == 5
    assert datetime.fromisoformat(body["items"][0]["performed_at"]) == DAY + timedelta(2)


def test_history_is_filtered_by_session_time(
    logged_in_client: TestClient, db_session: Session, current_user: User, squat: Exercise
) -> None:
    make_sessions(db_session, current_user, squat, [1], [2], [3], [4])
    params = {"since": (DAY + timedelta(1)).isoformat(), "until": (DAY + timedelta(3)).isoformat()}

    body = logged_in_client.get(history_path(squat), params=params).json()

    # since is inclusive, until is not
    assert reps(body) == [3, 2]
    assert body["total"] == 2


def test_history_pages_back_without_splitting_a_session(
    logged_in_client: TestClient, db_session: Session, current_user: User, squat: Exercise
) -> None:
    make_sessions(db_session, current_user, squat, [1], [2, 3, 4], [5])
    pages = []
    params: dict[str, object] = {"limit": 2}
    while True:
        body = logged_in_client.get(history_path(squat), params=params).json()
        if not body["items"]:
            break
        pages.append(reps(body))
        params = {"limit": 2, "before": body["items"][-1]["performed_at"]}

    assert pages == [[5, 2, 3, 4], [1]]


def test_history_of_an_invisible_exercise_is_not_found(
    logged_in_client: TestClient, db_session: Session
) -> None:
    theirs = create_exercise(db_session, owner=create_user(db_session))

    assert_error(logged_in_client.get(history_path(theirs)), 404, "not_found")
    assert_error(logged_in_client.get(f"{history_path(theirs)}/new"), 404, "not_found")


def test_history_times_need_a_timezone(logged_in_client: TestClient, squat: Exercise) -> None:
    response = logged_in_client.get(history_path(squat), params={"since": "2026-11-02T18:00:00"})

    assert_error(response, 422, "invalid")


# The logging form


def test_new_suggests_the_latest_record(
    logged_in_client: TestClient, db_session: Session, current_user: User, squat: Exercise
) -> None:
    older, newer = make_sessions(db_session, current_user, squat, [5], [3])
    create_set_record(
        db_session, newer, exercise=squat, reps=2, weight=Decimal("110"), weight_unit="lb"
    )

    response = logged_in_client.get(f"{history_path(squat)}/new")

    assert response.status_code == 200, response.text
    assert response.json() == {
        "defaults": {"reps": 2, "weight": "110.00", "weight_unit": "lb"},
        "options": {"weight_unit": ["kg", "lb"]},
    }


def test_new_without_history_offers_the_preferred_unit(
    logged_in_client: TestClient, db_session: Session, current_user: User, squat: Exercise
) -> None:
    current_user.weight_unit = WeightUnit.LB
    db_session.flush()

    defaults = logged_in_client.get(f"{history_path(squat)}/new").json()["defaults"]

    assert defaults == {"reps": None, "weight": None, "weight_unit": "lb"}


def test_new_for_a_prescribed_set_offers_its_targets(
    logged_in_client: TestClient,
    db_session: Session,
    planned: tuple[WorkoutSession, list[Set]],
    squat: Exercise,
) -> None:
    _, (_, second) = planned
    other_exercise_set = create_set(db_session)
    db_session.expire_all()

    response = logged_in_client.get(f"{history_path(squat)}/new", params={"set_id": second.id})
    mismatched = logged_in_client.get(
        f"{history_path(squat)}/new", params={"set_id": other_exercise_set.id}
    )

    assert response.json()["defaults"] == {"reps": 3, "weight": "110.00", "weight_unit": "kg"}
    assert_error(mismatched, 422, "invalid")


def test_set_records_need_a_login(
    client: TestClient, freestyle: WorkoutSession, squat: Exercise
) -> None:
    assert_error(client.get(history_path(squat)), 401, "not_authenticated")
    assert_error(
        client.put(f"/api/set-records/{uuid.uuid4()}", json=record_body(freestyle, squat)),
        401,
        "not_authenticated",
    )
