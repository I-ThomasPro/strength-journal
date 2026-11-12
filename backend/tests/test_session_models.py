"""Routine cycles and workout sessions in the database"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.sessions import now
from app.models.routine_cycle import RoutineCycle
from app.models.workout_session import WorkoutSession
from tests.factories import (
    create_routine,
    create_routine_cycle,
    create_routine_workout,
    create_user,
    create_workout,
    create_workout_session,
)


def reload(db_session: Session, session: WorkoutSession) -> WorkoutSession:
    db_session.expire_all()
    reloaded = db_session.get(WorkoutSession, session.id)
    assert reloaded is not None
    return reloaded


# Cycles


def test_a_routine_has_only_one_open_cycle(db_session: Session) -> None:
    routine = create_routine(db_session)
    create_routine_cycle(db_session, routine)

    with pytest.raises(IntegrityError, match="uq_routine_cycles_routine_id_open"):
        create_routine_cycle(db_session, routine)


def test_completed_cycles_dont_count_as_open(db_session: Session) -> None:
    routine = create_routine(db_session)
    create_routine_cycle(db_session, routine, completed_at=now())
    create_routine_cycle(db_session, routine, completed_at=now())

    open_cycle = create_routine_cycle(db_session, routine)

    assert open_cycle.number == 3


def test_cycle_numbers_are_unique_per_routine(db_session: Session) -> None:
    routine = create_routine(db_session)
    create_routine_cycle(db_session, routine, number=1, completed_at=now())

    with pytest.raises(IntegrityError, match="uq_routine_cycles_routine_id_number"):
        create_routine_cycle(db_session, routine, number=1)


def test_cycle_numbers_start_at_one(db_session: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_routine_cycles_number_positive"):
        create_routine_cycle(db_session, number=0)


def test_deleting_a_routine_deletes_its_cycles(db_session: Session) -> None:
    cycle = create_routine_cycle(db_session)
    cycle_id = cycle.id

    db_session.delete(cycle.routine)
    db_session.flush()
    db_session.expunge_all()

    assert db_session.get(RoutineCycle, cycle_id) is None


# Sessions


def test_a_session_from_a_slot_has_its_workout_and_cycle(db_session: Session) -> None:
    slot = create_routine_workout(db_session)

    session = reload(db_session, create_workout_session(db_session, routine_workout=slot))

    assert session.workout_id == slot.workout_id
    assert session.cycle is not None and session.cycle.routine_id == slot.routine_id
    assert session.completed is False
    assert session.performed_at is not None


def test_a_freestyle_session_has_no_slot_workout_or_cycle(db_session: Session) -> None:
    session = reload(db_session, create_workout_session(db_session))

    assert (session.routine_workout_id, session.workout_id, session.cycle_id) == (None, None, None)


def test_removing_a_slot_keeps_the_session_and_its_workout(db_session: Session) -> None:
    slot = create_routine_workout(db_session)
    session = create_workout_session(db_session, routine_workout=slot)

    db_session.delete(slot)
    db_session.flush()

    reloaded = reload(db_session, session)
    assert reloaded.routine_workout_id is None
    assert reloaded.workout_id == slot.workout_id
    assert reloaded.cycle_id is not None


def test_deleting_the_routine_keeps_the_session(db_session: Session) -> None:
    routine = create_routine(db_session)
    slot = create_routine_workout(db_session, create_workout(db_session, routine))
    session = create_workout_session(db_session, routine_workout=slot)

    db_session.delete(routine)
    db_session.flush()

    reloaded = reload(db_session, session)
    assert (reloaded.routine_workout_id, reloaded.workout_id, reloaded.cycle_id) == (
        None,
        None,
        None,
    )


def test_deleting_a_user_deletes_their_sessions(db_session: Session) -> None:
    user = create_user(db_session)
    session = create_workout_session(db_session, user=user)
    session_id = session.id

    db_session.delete(user)
    db_session.flush()
    db_session.expunge_all()

    assert db_session.get(WorkoutSession, session_id) is None
