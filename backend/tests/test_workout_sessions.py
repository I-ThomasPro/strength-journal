"""Workout sessions through the API, and how they move a routine through its cycle"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.sessions import now
from app.models.routine import Routine
from app.models.routine_workout import RoutineWorkout
from app.models.user import User
from app.models.workout_session import WorkoutSession
from tests.factories import (
    create_routine,
    create_routine_cycle,
    create_routine_workout,
    create_user,
    create_workout,
    create_workout_session,
)
from tests.helpers import assert_error

DAY = datetime(2026, 11, 2, 18, 0, tzinfo=UTC)


@pytest.fixture
def routine(db_session: Session, current_user: User) -> Routine:
    return create_routine(db_session, owner=current_user)


@pytest.fixture
def slot(db_session: Session, routine: Routine) -> RoutineWorkout:
    return create_routine_workout(db_session, create_workout(db_session, routine, name="Day A"))


def session_path(id: uuid.UUID | None = None) -> str:
    return f"/api/workout-sessions/{id or uuid.uuid4()}"


def count_sessions(db_session: Session) -> int:
    db_session.expire_all()
    return db_session.scalar(select(func.count()).select_from(WorkoutSession)) or 0


# Creating and changing sessions with PUT


def test_put_creates_a_freestyle_session(logged_in_client: TestClient) -> None:
    started = now()

    response = logged_in_client.put(session_path(), json={})

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["routine_workout"], body["workout"], body["cycle"]) == (None, None, None)
    assert body["completed"] is False
    performed_at = datetime.fromisoformat(body["performed_at"])
    assert started - timedelta(seconds=5) <= performed_at <= now() + timedelta(seconds=5)


def test_a_session_from_a_slot_gets_its_workout_and_open_cycle(
    logged_in_client: TestClient, db_session: Session, routine: Routine, slot: RoutineWorkout
) -> None:
    cycle = create_routine_cycle(db_session, routine)

    response = logged_in_client.put(session_path(), json={"routine_workout_id": str(slot.id)})

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["routine_workout"] == {"id": str(slot.id), "position": 0}
    assert body["workout"] == {"id": str(slot.workout_id), "name": "Day A"}
    assert body["cycle"] == {"id": str(cycle.id), "routine_id": str(routine.id), "number": 1}


def test_put_again_changes_only_what_it_sends(
    logged_in_client: TestClient, db_session: Session, slot: RoutineWorkout
) -> None:
    path = session_path()
    body = {"routine_workout_id": str(slot.id), "performed_at": DAY.isoformat()}

    created = logged_in_client.put(path, json=body)
    retried = logged_in_client.put(path, json=body)
    completed = logged_in_client.put(path, json={"completed": True})

    assert [r.status_code for r in (created, retried, completed)] == [201, 200, 200]
    assert completed.json()["completed"] is True
    assert completed.json()["routine_workout"]["id"] == str(slot.id)
    assert datetime.fromisoformat(completed.json()["performed_at"]) == DAY
    assert count_sessions(db_session) == 1


def test_a_retry_doesnt_move_a_session_into_a_newer_cycle(
    logged_in_client: TestClient, db_session: Session, routine: Routine, slot: RoutineWorkout
) -> None:
    first = create_routine_cycle(db_session, routine)
    path = session_path()
    body = {"routine_workout_id": str(slot.id)}
    logged_in_client.put(path, json=body)
    first.completed_at = now()
    create_routine_cycle(db_session, routine)

    retried = logged_in_client.put(path, json=body)

    assert retried.json()["cycle"]["number"] == 1


def test_a_session_can_be_made_freestyle(
    logged_in_client: TestClient, slot: RoutineWorkout
) -> None:
    path = session_path()
    logged_in_client.put(path, json={"routine_workout_id": str(slot.id)})

    body = logged_in_client.put(path, json={"routine_workout_id": None}).json()

    assert (body["routine_workout"], body["workout"], body["cycle"]) == (None, None, None)


def test_another_users_session_id_is_a_409(
    logged_in_client: TestClient, db_session: Session
) -> None:
    theirs = create_workout_session(db_session, user=create_user(db_session))

    assert_error(logged_in_client.put(session_path(theirs.id), json={}), 409, "id_conflict")
    db_session.expire_all()
    assert db_session.get(WorkoutSession, theirs.id).completed is False


def test_a_library_slot_must_be_copied_first(
    logged_in_client: TestClient, db_session: Session
) -> None:
    library_slot = create_routine_workout(db_session)

    response = logged_in_client.put(
        session_path(), json={"routine_workout_id": str(library_slot.id)}
    )

    assert_error(response, 403, "read_only")
    assert count_sessions(db_session) == 0


def test_another_users_or_an_unknown_slot_is_not_found(
    logged_in_client: TestClient, db_session: Session
) -> None:
    theirs = create_routine(db_session, owner=create_user(db_session))
    their_slot = create_routine_workout(db_session, create_workout(db_session, theirs))

    for slot_id in [their_slot.id, uuid.uuid4()]:
        response = logged_in_client.put(session_path(), json={"routine_workout_id": str(slot_id)})
        assert_error(response, 404, "not_found")
    assert count_sessions(db_session) == 0


@pytest.mark.parametrize(
    "body",
    [
        {"performed_at": "2026-11-02T18:00:00"},
        {"performed_at": None},
        {"completed": None},
        {"routine_workout_id": "x"},
    ],
)
def test_invalid_sessions_are_rejected(logged_in_client: TestClient, body: dict) -> None:
    assert_error(logged_in_client.put(session_path(), json=body), 422, "invalid")


# Reading, changing and deleting


def test_listing_the_users_sessions_newest_first(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    older = create_workout_session(db_session, user=current_user, performed_at=DAY)
    newer = create_workout_session(
        db_session, user=current_user, performed_at=DAY + timedelta(days=1)
    )
    create_workout_session(db_session, user=create_user(db_session))

    body = logged_in_client.get("/api/workout-sessions").json()

    assert [item["id"] for item in body["items"]] == [str(newer.id), str(older.id)]
    assert body["total"] == 2


def test_back_dating_and_completing_a_session(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    session = create_workout_session(db_session, user=current_user)
    path = session_path(session.id)

    dated = logged_in_client.patch(path, json={"performed_at": DAY.isoformat()})
    completed = logged_in_client.patch(path, json={"completed": True})

    assert dated.status_code == 200, dated.text
    assert datetime.fromisoformat(completed.json()["performed_at"]) == DAY
    assert completed.json()["completed"] is True
    assert logged_in_client.get(path).json()["completed"] is True


def test_deleting_a_session(
    logged_in_client: TestClient, db_session: Session, current_user: User
) -> None:
    session = create_workout_session(db_session, user=current_user)

    assert logged_in_client.delete(session_path(session.id)).status_code == 204
    assert count_sessions(db_session) == 0


def test_another_users_session_is_not_found(
    logged_in_client: TestClient, db_session: Session
) -> None:
    theirs = create_workout_session(db_session, user=create_user(db_session))
    path = session_path(theirs.id)

    assert_error(logged_in_client.get(path), 404, "not_found")
    assert_error(logged_in_client.patch(path, json={"completed": True}), 404, "not_found")
    assert_error(logged_in_client.delete(path), 404, "not_found")
    assert_error(logged_in_client.get(session_path()), 404, "not_found")
    assert count_sessions(db_session) == 1


# Cycles in the routine detail


def test_new_and_copied_routines_start_at_cycle_one(logged_in_client: TestClient) -> None:
    created = logged_in_client.post("/api/routines", json={"name": "Upper Lower"}).json()
    copied = logged_in_client.post(f"/api/routines/{created['id']}/copy", json={}).json()

    for routine in [created, copied]:
        assert routine["current_cycle"]["number"] == 1
        assert routine["current_cycle"]["completed_at"] is None


def test_the_next_slot_follows_completed_sessions_through_the_cycle(
    logged_in_client: TestClient, db_session: Session, current_user: User, routine: Routine
) -> None:
    day_a = create_workout(db_session, routine, name="Day A")
    day_b = create_workout(db_session, routine, name="Day B")
    slots = [create_routine_workout(db_session, workout) for workout in (day_a, day_b, day_a)]
    create_routine_cycle(db_session, routine)
    path = f"/api/routines/{routine.id}"

    def next_slot() -> dict | None:
        return logged_in_client.get(path).json()["next_slot"]

    assert next_slot()["id"] == str(slots[0].id)
    for index, slot in enumerate(slots):
        # An unfinished session doesn't move the cycle on
        session_id = uuid.uuid4()
        body = {
            "routine_workout_id": str(slot.id),
            "performed_at": (DAY + timedelta(index)).isoformat(),
        }
        logged_in_client.put(session_path(session_id), json=body)
        assert next_slot()["id"] == str(slot.id)

        logged_in_client.patch(session_path(session_id), json={"completed": True})

        expected = slots[index + 1] if index + 1 < len(slots) else None
        assert (next_slot() or {}).get("id") == (str(expected.id) if expected else None)
    assert logged_in_client.get(path).json()["next_slot"] is None


def test_the_next_slot_ignores_other_users_and_freestyle_sessions(
    logged_in_client: TestClient, db_session: Session, current_user: User, routine: Routine
) -> None:
    first = create_routine_workout(db_session, create_workout(db_session, routine))
    create_routine_workout(db_session, create_workout(db_session, routine))
    create_workout_session(db_session, user=current_user, completed=True)
    create_workout_session(
        db_session, user=create_user(db_session), routine_workout=first, completed=True
    )

    body = logged_in_client.get(f"/api/routines/{routine.id}").json()

    assert body["next_slot"]["id"] == str(first.id)


def test_sessions_need_a_login(client: TestClient) -> None:
    assert_error(client.get("/api/workout-sessions"), 401, "not_authenticated")
    assert_error(client.put(session_path(), json={}), 401, "not_authenticated")
