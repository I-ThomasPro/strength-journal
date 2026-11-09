from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.common import WeightUnit
from app.models.progression import Progression, ProgressionCondition
from tests.factories import create_exercise, create_progression, create_routine


def test_progression_links_a_routine_and_exercise_with_defaults(db_session: Session) -> None:
    routine = create_routine(db_session)
    squat = create_exercise(db_session, name="Squat")
    progression = create_progression(
        db_session, routine=routine, exercise=squat, increment=Decimal("5"), increment_unit="lb"
    )
    db_session.refresh(progression)

    assert progression.routine is routine
    assert progression.exercise is squat
    assert progression.increment == Decimal("5.00")
    assert progression.increment_unit is WeightUnit.LB
    assert progression.condition is ProgressionCondition.ALL_SETS_COMPLETED


def test_second_progression_for_the_same_routine_and_exercise_is_rejected(
    db_session: Session,
) -> None:
    routine = create_routine(db_session)
    squat = create_exercise(db_session)
    create_progression(db_session, routine=routine, exercise=squat)

    with pytest.raises(IntegrityError, match="uq_progressions_routine_id_exercise_id"):
        create_progression(db_session, routine=routine, exercise=squat)


def test_same_exercise_can_progress_in_different_routines(db_session: Session) -> None:
    squat = create_exercise(db_session)
    create_progression(db_session, exercise=squat)
    create_progression(db_session, exercise=squat)


@pytest.mark.parametrize("increment", [Decimal("0"), Decimal("-2.5")])
def test_non_positive_increment_is_rejected(db_session: Session, increment: Decimal) -> None:
    with pytest.raises(IntegrityError, match="ck_progressions_increment_positive"):
        create_progression(db_session, increment=increment)


@pytest.mark.parametrize("unit", ["stone", "KG", ""])
def test_invalid_increment_unit_is_rejected(db_session: Session, unit: str) -> None:
    with pytest.raises(IntegrityError, match="ck_progressions_increment_unit"):
        create_progression(db_session, increment_unit=unit)


@pytest.mark.parametrize("condition", ["any_set_completed", "ALL_SETS_COMPLETED", ""])
def test_invalid_condition_is_rejected(db_session: Session, condition: str) -> None:
    with pytest.raises(IntegrityError, match="ck_progressions_condition"):
        create_progression(db_session, condition=condition)


def test_deleting_a_routine_deletes_its_progressions(db_session: Session) -> None:
    progression = create_progression(db_session)
    progression_id, exercise = progression.id, progression.exercise

    db_session.delete(progression.routine)
    db_session.flush()
    db_session.expunge_all()

    assert db_session.get(Progression, progression_id) is None
    assert db_session.get(type(exercise), exercise.id) is not None


def test_deleting_an_exercise_with_a_progression_is_rejected(db_session: Session) -> None:
    progression = create_progression(db_session)

    db_session.delete(progression.exercise)
    with pytest.raises(IntegrityError, match="fk_progressions_exercise_id_exercises"):
        db_session.flush()
