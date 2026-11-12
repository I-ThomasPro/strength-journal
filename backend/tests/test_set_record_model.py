from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.common import WeightUnit
from app.models.exercise import Exercise
from app.models.set_record import SetRecord
from tests.factories import (
    create_exercise,
    create_routine,
    create_set,
    create_set_record,
    create_user,
    create_workout,
    create_workout_exercise,
    create_workout_session,
)
from tests.helpers import check_deferred_constraints


def test_a_record_belongs_to_a_session_and_an_exercise(db_session: Session) -> None:
    workout_session = create_workout_session(db_session)
    squat = create_exercise(db_session, name="Squat")

    record = create_set_record(db_session, workout_session, exercise=squat)
    db_session.expire_all()

    assert record.session.id == workout_session.id
    assert record.exercise.name == "Squat"
    assert record.performed_at == workout_session.performed_at
    assert (record.set_id, record.target_reps, record.target_weight) == (None, None, None)


def test_a_sessions_records_are_ordered_by_position(db_session: Session) -> None:
    workout_session = create_workout_session(db_session)
    for reps, position in [(3, 2), (5, 0), (4, 1)]:
        create_set_record(db_session, workout_session, reps=reps, position=position)
    check_deferred_constraints(db_session)
    db_session.expire_all()

    assert [record.reps for record in workout_session.set_records] == [5, 4, 3]


def test_record_positions_can_be_swapped_in_one_transaction(db_session: Session) -> None:
    workout_session = create_workout_session(db_session)
    first = create_set_record(db_session, workout_session, reps=1)
    second = create_set_record(db_session, workout_session, reps=2)

    first.position, second.position = 1, 0
    db_session.flush()
    check_deferred_constraints(db_session)
    db_session.expire_all()

    assert [record.reps for record in workout_session.set_records] == [2, 1]


def test_duplicate_position_in_a_session_is_rejected(db_session: Session) -> None:
    workout_session = create_workout_session(db_session)
    create_set_record(db_session, workout_session, position=0)
    create_set_record(db_session, workout_session, position=0)

    with pytest.raises(IntegrityError, match="uq_set_records_session_id_position"):
        check_deferred_constraints(db_session)


def test_negative_position_is_rejected(db_session: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_set_records_position_non_negative"):
        create_set_record(db_session, position=-1)


@pytest.mark.parametrize(
    "targets",
    [
        {"target_reps": 5},
        {"target_reps": 5, "target_weight": Decimal("60")},
        {"target_weight": Decimal("60"), "target_unit": WeightUnit.KG},
    ],
)
def test_targets_are_all_set_or_all_null(db_session: Session, targets: dict) -> None:
    with pytest.raises(IntegrityError, match="ck_set_records_targets_all_or_none"):
        create_set_record(db_session, **targets)


def test_deleting_a_session_deletes_its_records(db_session: Session) -> None:
    record = create_set_record(db_session)
    record_id = record.id

    db_session.delete(record.session)
    db_session.flush()
    db_session.expunge_all()

    assert db_session.get(SetRecord, record_id) is None


def test_deleting_a_set_keeps_its_records_and_their_targets(db_session: Session) -> None:
    set_ = create_set(db_session, target_reps=5, target_weight=Decimal("100"))
    record = create_set_record(
        db_session,
        set=set_,
        target_reps=5,
        target_weight=Decimal("100"),
        target_unit=WeightUnit.KG,
    )

    db_session.delete(set_)
    db_session.flush()
    db_session.expire_all()

    kept = db_session.get(SetRecord, record.id)
    assert kept is not None and kept.set_id is None
    assert (kept.target_reps, kept.target_weight, kept.target_unit) == (
        5,
        Decimal("100.00"),
        WeightUnit.KG,
    )


def test_zero_reps_and_zero_weight_are_allowed(db_session: Session) -> None:
    record = create_set_record(db_session, reps=0, weight=Decimal("0"))
    db_session.refresh(record)

    assert (record.reps, record.weight) == (0, Decimal("0.00"))


def test_negative_reps_are_rejected(db_session: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_set_records_reps_non_negative"):
        create_set_record(db_session, reps=-1)


def test_negative_weight_is_rejected(db_session: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_set_records_weight_non_negative"):
        create_set_record(db_session, weight=Decimal("-2.5"))


@pytest.mark.parametrize("unit", ["stone", "KG", ""])
def test_invalid_weight_unit_is_rejected(db_session: Session, unit: str) -> None:
    with pytest.raises(IntegrityError, match="ck_set_records_weight_unit"):
        create_set_record(db_session, weight_unit=unit)


def test_deleting_a_user_deletes_their_records(db_session: Session) -> None:
    user = create_user(db_session)
    custom = create_exercise(db_session, owner=user)
    library = create_exercise(db_session)
    own_record = create_set_record(db_session, user=user, exercise=custom)
    library_record = create_set_record(db_session, user=user, exercise=library)
    other_record = create_set_record(db_session, exercise=library)
    ids = (own_record.id, library_record.id, other_record.id, custom.id, library.id)

    db_session.delete(user)
    db_session.flush()
    check_deferred_constraints(db_session)
    db_session.expunge_all()

    own_id, library_record_id, other_id, custom_id, library_id = ids
    assert db_session.get(SetRecord, own_id) is None
    assert db_session.get(SetRecord, library_record_id) is None
    assert db_session.get(Exercise, custom_id) is None
    assert db_session.get(SetRecord, other_id) is not None
    assert db_session.get(Exercise, library_id) is not None


def test_deleting_an_exercise_with_records_is_rejected_at_commit(db_session: Session) -> None:
    record = create_set_record(db_session)

    db_session.delete(record.exercise)
    db_session.flush()
    with pytest.raises(IntegrityError, match="fk_set_records_exercise_id_exercises"):
        check_deferred_constraints(db_session)


def test_deleting_a_routine_workout_or_set_leaves_records_untouched(db_session: Session) -> None:
    user = create_user(db_session)
    squat = create_exercise(db_session)
    routine = create_routine(db_session, owner=user)
    workout = create_workout(db_session, routine)
    entry = create_workout_exercise(db_session, workout, squat)
    set_ = create_set(db_session, entry)
    record = create_set_record(db_session, user=user, exercise=squat)
    record_id = record.id

    db_session.delete(set_)
    db_session.flush()
    db_session.delete(workout)
    db_session.flush()
    db_session.delete(routine)
    db_session.flush()
    check_deferred_constraints(db_session)
    db_session.expunge_all()

    assert db_session.get(SetRecord, record_id) is not None
