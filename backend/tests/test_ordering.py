"""Positions for ordered children, using workouts as the example"""

from sqlalchemy.orm import Session

from app.models import ordering
from app.models.workout import Workout
from tests.factories import create_routine, create_workout
from tests.helpers import check_deferred_constraints


def make_workouts(db_session: Session, *names: str) -> list[Workout]:
    routine = create_routine(db_session)
    return [create_workout(db_session, routine, name=name) for name in names]


def names(workouts: list[Workout]) -> list[str]:
    return [workout.name for workout in workouts]


def positions(workouts: list[Workout]) -> list[int]:
    return [workout.position for workout in workouts]


def test_place_appends_when_no_position_is_given(db_session: Session) -> None:
    a, b = make_workouts(db_session, "A", "B")
    c = Workout(routine=a.routine, name="C", position=-1)

    order = ordering.place([a, b], c)
    db_session.add(c)
    db_session.flush()
    check_deferred_constraints(db_session)

    assert (names(order), positions(order)) == (["A", "B", "C"], [0, 1, 2])


def test_place_inserts_and_shifts_later_siblings(db_session: Session) -> None:
    a, b = make_workouts(db_session, "A", "B")
    c = Workout(routine=a.routine, name="C", position=-1)

    order = ordering.place([a, b], c, 0)
    db_session.add(c)
    db_session.flush()
    check_deferred_constraints(db_session)

    assert (names(order), positions(order)) == (["C", "A", "B"], [0, 1, 2])


def test_place_moves_forwards_and_backwards(db_session: Session) -> None:
    a, b, c, d = make_workouts(db_session, "A", "B", "C", "D")

    forwards = ordering.place([a, b, c, d], a, 2)
    db_session.flush()
    backwards = ordering.place(forwards, d, 0)
    db_session.flush()
    check_deferred_constraints(db_session)

    assert names(forwards) == ["B", "C", "A", "D"]
    assert (names(backwards), positions(backwards)) == (["D", "B", "C", "A"], [0, 1, 2, 3])


def test_place_clamps_positions_out_of_range(db_session: Session) -> None:
    a, b, c = make_workouts(db_session, "A", "B", "C")

    assert names(ordering.place([a, b, c], a, 99)) == ["B", "C", "A"]
    assert names(ordering.place([b, c, a], a, -5)) == ["A", "B", "C"]


def test_remove_closes_the_gap(db_session: Session) -> None:
    a, b, c = make_workouts(db_session, "A", "B", "C")

    order = ordering.remove([a, b, c], b)
    db_session.delete(b)
    db_session.flush()
    check_deferred_constraints(db_session)

    assert (names(order), positions(order)) == (["A", "C"], [0, 1])
