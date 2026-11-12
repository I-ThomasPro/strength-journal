"""A routine's cycle: slots saying which of its workouts comes at each position"""

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.routine_workout import RoutineWorkout
from tests.factories import create_routine, create_routine_workout, create_workout
from tests.helpers import check_deferred_constraints


def test_a_cycle_is_ordered_by_position_and_can_repeat_a_workout(db_session: Session) -> None:
    routine = create_routine(db_session)
    day_a = create_workout(db_session, routine, name="Day A")
    day_b = create_workout(db_session, routine, name="Day B")
    create_routine_workout(db_session, day_a, position=2)
    create_routine_workout(db_session, day_a, position=0)
    create_routine_workout(db_session, day_b, position=1)
    check_deferred_constraints(db_session)
    db_session.expire(routine)

    assert [slot.workout.name for slot in routine.slots] == ["Day A", "Day B", "Day A"]
    assert all(slot.routine is routine for slot in routine.slots)


def test_a_slot_cant_point_at_another_routines_workout(db_session: Session) -> None:
    routine = create_routine(db_session)
    elsewhere = create_workout(db_session, create_routine(db_session))

    with pytest.raises(IntegrityError, match="fk_routine_workouts_routine_id_workout_id_workouts"):
        create_routine_workout(db_session, elsewhere, routine_id=routine.id)


def test_duplicate_slot_position_in_a_routine_is_rejected(db_session: Session) -> None:
    workout = create_workout(db_session)
    create_routine_workout(db_session, workout, position=0)
    create_routine_workout(db_session, workout, position=0)

    with pytest.raises(IntegrityError, match="uq_routine_workouts_routine_id_position"):
        check_deferred_constraints(db_session)


def test_same_slot_position_in_different_routines_is_allowed(db_session: Session) -> None:
    create_routine_workout(db_session, create_workout(db_session), position=0)
    create_routine_workout(db_session, create_workout(db_session), position=0)

    check_deferred_constraints(db_session)


def test_slot_positions_can_be_swapped_in_one_transaction(db_session: Session) -> None:
    routine = create_routine(db_session)
    first = create_routine_workout(db_session, create_workout(db_session, routine, name="A"))
    second = create_routine_workout(db_session, create_workout(db_session, routine, name="B"))

    first.position, second.position = 1, 0
    db_session.flush()
    check_deferred_constraints(db_session)
    db_session.expire(routine)

    assert [slot.workout.name for slot in routine.slots] == ["B", "A"]


def test_negative_slot_position_is_rejected(db_session: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_routine_workouts_position_non_negative"):
        create_routine_workout(db_session, position=-1)


def test_deleting_a_workout_deletes_its_slots(db_session: Session) -> None:
    routine = create_routine(db_session)
    workout = create_workout(db_session, routine)
    kept = create_routine_workout(db_session, create_workout(db_session, routine))
    create_routine_workout(db_session, workout)
    create_routine_workout(db_session, workout)

    db_session.delete(workout)
    db_session.flush()
    db_session.expunge_all()

    remaining = db_session.scalars(
        select(RoutineWorkout.id).where(RoutineWorkout.routine_id == routine.id)
    )
    assert list(remaining) == [kept.id]


def test_deleting_a_routine_deletes_its_slots(db_session: Session) -> None:
    slot = create_routine_workout(db_session)
    slot_id = slot.id

    db_session.delete(slot.routine)
    db_session.flush()
    db_session.expunge_all()

    assert db_session.get(RoutineWorkout, slot_id) is None
