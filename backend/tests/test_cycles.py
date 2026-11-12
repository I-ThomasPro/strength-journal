"""Starting a routine's next cycle, carrying the weights the user lifted into its plan"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.sessions import now
from app.models.common import WeightUnit
from app.models.routine import Routine
from app.models.routine_cycle import RoutineCycle
from app.models.routine_workout import RoutineWorkout
from app.models.set import Set
from app.models.user import User
from tests.factories import (
    create_routine,
    create_routine_cycle,
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


@dataclass
class Plan:
    """A routine cycling A, B, A: Day A prescribes two squat sets, Day B one bench set"""

    routine: Routine
    cycle: RoutineCycle
    slots: list[RoutineWorkout]
    squat_sets: list[Set]
    bench_set: Set


@pytest.fixture
def plan(db_session: Session, current_user: User) -> Plan:
    routine = create_routine(db_session, owner=current_user)
    day_a = create_workout(db_session, routine, name="Day A")
    day_b = create_workout(db_session, routine, name="Day B")
    squat = create_workout_exercise(db_session, day_a)
    bench = create_workout_exercise(db_session, day_b)
    squat_sets = [
        create_set(db_session, squat, target_reps=5, target_weight=Decimal("100")),
        create_set(db_session, squat, target_reps=5, target_weight=Decimal("100")),
    ]
    bench_set = create_set(db_session, bench, target_reps=8, target_weight=Decimal("60"))
    slots = [create_routine_workout(db_session, workout) for workout in (day_a, day_b, day_a)]
    cycle = create_routine_cycle(db_session, routine)
    return Plan(routine, cycle, slots, squat_sets, bench_set)


def do_session(
    db_session: Session,
    user: User,
    slot: RoutineWorkout,
    day: int,
    lifts: list[tuple[Set | None, int, str]],
    completed: bool = True,
    unit: WeightUnit = WeightUnit.KG,
) -> None:
    """A session from `slot` on DAY + `day`, logging (set, reps, weight) in order"""
    session = create_workout_session(
        db_session,
        user=user,
        routine_workout=slot,
        performed_at=DAY + timedelta(days=day),
        completed=completed,
    )
    for set_, reps, weight in lifts:
        create_set_record(
            db_session,
            session,
            exercise_id=slot.workout.exercises[0].exercise_id,
            set=set_,
            reps=reps,
            weight=Decimal(weight),
            weight_unit=unit,
        )


def targets(db_session: Session, *sets: Set) -> list[tuple[int, Decimal, WeightUnit]]:
    db_session.expire_all()
    return [
        (s.target_reps, s.target_weight, s.weight_unit)
        for s in (db_session.get(Set, set_.id) for set_ in sets)
    ]


def start_next_cycle(client: TestClient, routine: Routine, db_session: Session) -> dict:
    # As a real request would, read stored NUMERIC(6, 2) values rather than the factories'
    db_session.expire_all()
    response = client.post(f"/api/routines/{routine.id}/cycles")
    assert response.status_code == 201, response.text
    return response.json()


def test_weight_and_unit_are_carried_forward_and_reps_arent(
    logged_in_client: TestClient, db_session: Session, current_user: User, plan: Plan
) -> None:
    first, second = plan.squat_sets
    do_session(
        db_session,
        current_user,
        plan.slots[0],
        0,
        [(first, 5, "225"), (second, 3, "225")],
        unit=WeightUnit.LB,
    )

    body = start_next_cycle(logged_in_client, plan.routine, db_session)

    assert targets(db_session, first, second) == [
        (5, Decimal("225.00"), WeightUnit.LB),
        (5, Decimal("225.00"), WeightUnit.LB),
    ]
    assert sorted(change["set_id"] for change in body["changed_sets"]) == sorted(
        [str(first.id), str(second.id)]
    )
    assert body["changed_sets"][0] | {"set_id": None} == {
        "set_id": None,
        "workout_exercise_id": str(first.workout_exercise_id),
        "from_weight": "100.00",
        "from_unit": "kg",
        "to_weight": "225.00",
        "to_unit": "lb",
    }


def test_a_repeated_workout_takes_the_later_sessions_record(
    logged_in_client: TestClient, db_session: Session, current_user: User, plan: Plan
) -> None:
    first, _ = plan.squat_sets
    do_session(db_session, current_user, plan.slots[0], 0, [(first, 5, "105")])
    do_session(db_session, current_user, plan.slots[2], 2, [(first, 5, "110")])

    start_next_cycle(logged_in_client, plan.routine, db_session)

    assert targets(db_session, first) == [(5, Decimal("110.00"), WeightUnit.KG)]


def test_within_a_session_the_later_record_wins(
    logged_in_client: TestClient, db_session: Session, current_user: User, plan: Plan
) -> None:
    first, _ = plan.squat_sets
    do_session(db_session, current_user, plan.slots[0], 0, [(first, 5, "105"), (first, 2, "120")])

    start_next_cycle(logged_in_client, plan.routine, db_session)

    assert targets(db_session, first) == [(5, Decimal("120.00"), WeightUnit.KG)]


def test_incomplete_sessions_and_earlier_cycles_are_ignored(
    logged_in_client: TestClient, db_session: Session, current_user: User, plan: Plan
) -> None:
    first, second = plan.squat_sets
    # An earlier cycle's record, then this cycle's unfinished session
    do_session(db_session, current_user, plan.slots[0], 0, [(first, 5, "150")])
    plan.cycle.completed_at = now()
    create_routine_cycle(db_session, plan.routine)
    do_session(db_session, current_user, plan.slots[0], 3, [(second, 5, "140")], completed=False)

    body = start_next_cycle(logged_in_client, plan.routine, db_session)

    assert body["changed_sets"] == []
    assert targets(db_session, first, second) == [(5, Decimal("100.00"), WeightUnit.KG)] * 2


def test_unlinked_records_and_unrecorded_sets_change_nothing(
    logged_in_client: TestClient, db_session: Session, current_user: User, plan: Plan
) -> None:
    first, second = plan.squat_sets
    do_session(db_session, current_user, plan.slots[0], 0, [(first, 5, "100"), (None, 5, "130")])

    body = start_next_cycle(logged_in_client, plan.routine, db_session)

    # The record matching its target isn't a change, and nothing else was linked
    assert body["changed_sets"] == []
    assert targets(db_session, first, second, plan.bench_set) == [
        (5, Decimal("100.00"), WeightUnit.KG),
        (5, Decimal("100.00"), WeightUnit.KG),
        (8, Decimal("60.00"), WeightUnit.KG),
    ]


def test_the_current_cycle_closes_and_the_next_opens(
    logged_in_client: TestClient, db_session: Session, plan: Plan
) -> None:
    body = start_next_cycle(logged_in_client, plan.routine, db_session)
    again = start_next_cycle(logged_in_client, plan.routine, db_session)

    assert (body["number"], body["completed_at"]) == (2, None)
    assert again["number"] == 3
    db_session.expire_all()
    cycles = db_session.scalars(
        select(RoutineCycle)
        .where(RoutineCycle.routine_id == plan.routine.id)
        .order_by(RoutineCycle.number)
    ).all()
    assert [(c.number, c.completed_at is None) for c in cycles] == [
        (1, False),
        (2, False),
        (3, True),
    ]


def test_the_next_cycle_starts_from_the_first_slot(
    logged_in_client: TestClient, db_session: Session, current_user: User, plan: Plan
) -> None:
    for day, slot in enumerate(plan.slots):
        do_session(db_session, current_user, slot, day, [])
    detail_path = f"/api/routines/{plan.routine.id}"
    assert logged_in_client.get(detail_path).json()["next_slot"] is None

    start_next_cycle(logged_in_client, plan.routine, db_session)

    detail = logged_in_client.get(detail_path).json()
    assert detail["current_cycle"]["number"] == 2
    assert detail["next_slot"]["id"] == str(plan.slots[0].id)


def test_listing_cycles_newest_first(
    logged_in_client: TestClient, db_session: Session, plan: Plan
) -> None:
    start_next_cycle(logged_in_client, plan.routine, db_session)

    body = logged_in_client.get(f"/api/routines/{plan.routine.id}/cycles").json()

    assert [cycle["number"] for cycle in body["items"]] == [2, 1]
    assert body["items"][1]["completed_at"] is not None
    assert body["total"] == 2


def test_a_library_routines_cycles_can_be_read_but_not_started(
    logged_in_client: TestClient, db_session: Session
) -> None:
    library = create_routine(db_session)
    create_routine_cycle(db_session, library)

    listed = logged_in_client.get(f"/api/routines/{library.id}/cycles")
    started = logged_in_client.post(f"/api/routines/{library.id}/cycles")

    assert listed.json()["total"] == 1
    assert_error(started, 403, "read_only")


def test_another_users_cycles_are_not_found(
    logged_in_client: TestClient, db_session: Session
) -> None:
    theirs = create_routine(db_session, owner=create_user(db_session))
    create_routine_cycle(db_session, theirs)
    path = f"/api/routines/{theirs.id}/cycles"

    assert_error(logged_in_client.get(path), 404, "not_found")
    assert_error(logged_in_client.post(path), 404, "not_found")
    db_session.expire_all()
    assert (
        db_session.scalar(select(RoutineCycle.number).where(RoutineCycle.routine_id == theirs.id))
        == 1
    )


def test_cycles_need_a_login(client: TestClient, plan: Plan) -> None:
    assert_error(client.post(f"/api/routines/{plan.routine.id}/cycles"), 401, "not_authenticated")
