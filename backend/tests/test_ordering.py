"""Positions for ordered children, using a routine's slots as the example"""

from sqlalchemy.orm import Session

from app.models import ordering
from app.models.routine_workout import RoutineWorkout
from tests.factories import create_routine, create_routine_workout, create_workout
from tests.helpers import check_deferred_constraints


def make_slots(db_session: Session, *names: str) -> list[RoutineWorkout]:
    """One slot per name, each for its own workout, in one routine's cycle"""
    routine = create_routine(db_session)
    return [
        create_routine_workout(db_session, create_workout(db_session, routine, name=name))
        for name in names
    ]


def new_slot(db_session: Session, sibling: RoutineWorkout, name: str) -> RoutineWorkout:
    """A slot not yet placed in `sibling`'s cycle"""
    workout = create_workout(db_session, sibling.routine, name=name)
    return RoutineWorkout(routine_id=sibling.routine_id, workout=workout, position=-1)


def names(slots: list[RoutineWorkout]) -> list[str]:
    return [slot.workout.name for slot in slots]


def positions(slots: list[RoutineWorkout]) -> list[int]:
    return [slot.position for slot in slots]


def test_place_appends_when_no_position_is_given(db_session: Session) -> None:
    a, b = make_slots(db_session, "A", "B")
    c = new_slot(db_session, a, "C")

    order = ordering.place([a, b], c)
    db_session.add(c)
    db_session.flush()
    check_deferred_constraints(db_session)

    assert (names(order), positions(order)) == (["A", "B", "C"], [0, 1, 2])


def test_place_inserts_and_shifts_later_siblings(db_session: Session) -> None:
    a, b = make_slots(db_session, "A", "B")
    c = new_slot(db_session, a, "C")

    order = ordering.place([a, b], c, 0)
    db_session.add(c)
    db_session.flush()
    check_deferred_constraints(db_session)

    assert (names(order), positions(order)) == (["C", "A", "B"], [0, 1, 2])


def test_place_moves_forwards_and_backwards(db_session: Session) -> None:
    a, b, c, d = make_slots(db_session, "A", "B", "C", "D")

    forwards = ordering.place([a, b, c, d], a, 2)
    db_session.flush()
    backwards = ordering.place(forwards, d, 0)
    db_session.flush()
    check_deferred_constraints(db_session)

    assert names(forwards) == ["B", "C", "A", "D"]
    assert (names(backwards), positions(backwards)) == (["D", "B", "C", "A"], [0, 1, 2, 3])


def test_place_clamps_positions_out_of_range(db_session: Session) -> None:
    a, b, c = make_slots(db_session, "A", "B", "C")

    assert names(ordering.place([a, b, c], a, 99)) == ["B", "C", "A"]
    assert names(ordering.place([b, c, a], a, -5)) == ["A", "B", "C"]


def test_remove_closes_the_gap(db_session: Session) -> None:
    a, b, c = make_slots(db_session, "A", "B", "C")

    order = ordering.remove([a, b, c], b)
    db_session.delete(b)
    db_session.flush()
    check_deferred_constraints(db_session)

    assert (names(order), positions(order)) == (["A", "C"], [0, 1])
