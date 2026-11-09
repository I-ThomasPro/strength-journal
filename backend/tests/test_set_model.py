from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.common import WeightUnit
from app.models.set import Set
from app.models.workout import WorkoutExercise
from tests.factories import create_set, create_workout, create_workout_exercise
from tests.helpers import check_deferred_constraints


def test_set_stores_its_targets(db_session: Session) -> None:
    entry = create_workout_exercise(db_session)
    set_ = create_set(
        db_session, entry, target_reps=8, target_weight=Decimal("102.5"), weight_unit="lb"
    )
    db_session.refresh(set_)

    assert set_.workout_exercise is entry
    assert set_.target_reps == 8
    assert set_.target_weight == Decimal("102.50")
    assert set_.weight_unit is WeightUnit.LB


def test_sets_are_returned_in_position_order(db_session: Session) -> None:
    entry = create_workout_exercise(db_session)
    create_set(db_session, entry, position=2, target_reps=3)
    create_set(db_session, entry, position=0, target_reps=5)
    create_set(db_session, entry, position=1, target_reps=4)
    db_session.expire(entry)

    assert [set_.target_reps for set_ in entry.sets] == [5, 4, 3]


def test_duplicate_position_for_a_workout_exercise_is_rejected(db_session: Session) -> None:
    entry = create_workout_exercise(db_session)
    create_set(db_session, entry, position=0)
    create_set(db_session, entry, position=0)

    with pytest.raises(IntegrityError, match="uq_sets_workout_exercise_id_position"):
        check_deferred_constraints(db_session)


def test_same_position_for_different_workout_exercises_is_allowed(db_session: Session) -> None:
    create_set(db_session, create_workout_exercise(db_session), position=0)
    create_set(db_session, create_workout_exercise(db_session), position=0)

    check_deferred_constraints(db_session)


def test_set_positions_can_be_swapped_in_one_transaction(db_session: Session) -> None:
    entry = create_workout_exercise(db_session)
    warm_up = create_set(db_session, entry, position=0, target_weight=Decimal("40"))
    working = create_set(db_session, entry, position=1, target_weight=Decimal("80"))

    warm_up.position, working.position = 1, 0
    db_session.flush()
    check_deferred_constraints(db_session)
    db_session.expire(entry)

    assert [set_.target_weight for set_ in entry.sets] == [Decimal("80.00"), Decimal("40.00")]


@pytest.mark.parametrize("reps", [0, -1])
def test_non_positive_reps_are_rejected(db_session: Session, reps: int) -> None:
    with pytest.raises(IntegrityError, match="ck_sets_target_reps_positive"):
        create_set(db_session, target_reps=reps)


def test_zero_weight_is_allowed(db_session: Session) -> None:
    set_ = create_set(db_session, target_weight=Decimal("0"))
    db_session.refresh(set_)

    assert set_.target_weight == Decimal("0.00")


def test_negative_weight_is_rejected(db_session: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_sets_target_weight_non_negative"):
        create_set(db_session, target_weight=Decimal("-2.5"))


@pytest.mark.parametrize("unit", ["stone", "KG", ""])
def test_invalid_weight_unit_is_rejected(db_session: Session, unit: str) -> None:
    with pytest.raises(IntegrityError, match="ck_sets_weight_unit"):
        create_set(db_session, weight_unit=unit)


def test_negative_position_is_rejected(db_session: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_sets_position_non_negative"):
        create_set(db_session, position=-1)


def test_deleting_a_workout_exercise_deletes_its_sets(db_session: Session) -> None:
    entry = create_workout_exercise(db_session)
    set_ids = [create_set(db_session, entry).id for _ in range(3)]
    other = create_set(db_session)

    db_session.delete(entry)
    db_session.flush()
    db_session.expunge_all()

    assert all(db_session.get(Set, set_id) is None for set_id in set_ids)
    assert db_session.get(Set, other.id) is not None


def test_deleting_a_routine_deletes_sets_all_the_way_down(db_session: Session) -> None:
    workout = create_workout(db_session)
    set_ = create_set(db_session, create_workout_exercise(db_session, workout))
    set_id, routine = set_.id, workout.routine

    db_session.delete(routine)
    db_session.flush()
    db_session.expunge_all()

    assert db_session.get(Set, set_id) is None


def test_removing_a_set_from_its_exercise_deletes_it(db_session: Session) -> None:
    entry = create_workout_exercise(db_session)
    set_ = create_set(db_session, entry)
    set_id = set_.id
    db_session.expire(entry)

    entry.sets.remove(db_session.get(Set, set_id))
    db_session.flush()

    assert db_session.get(Set, set_id) is None
    assert db_session.get(WorkoutExercise, entry.id) is not None
