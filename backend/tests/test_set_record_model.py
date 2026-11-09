from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
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
)
from tests.helpers import check_deferred_constraints


def test_record_links_a_user_and_an_exercise(db_session: Session) -> None:
    user = create_user(db_session)
    squat = create_exercise(db_session, name="Squat")
    record = create_set_record(
        db_session, user=user, exercise=squat, reps=8, weight=Decimal("102.5"), weight_unit="lb"
    )
    db_session.refresh(record)

    assert record.user is user
    assert record.exercise is squat
    assert record.reps == 8
    assert record.weight == Decimal("102.50")
    assert record.weight_unit is WeightUnit.LB


def test_performed_at_defaults_to_now(db_session: Session) -> None:
    before = datetime.now(UTC) - timedelta(minutes=1)
    record = create_set_record(db_session)
    db_session.refresh(record)

    assert record.performed_at.tzinfo is not None
    assert record.performed_at > before


def test_a_users_records_of_an_exercise_are_ordered_by_performed_at(db_session: Session) -> None:
    user = create_user(db_session)
    squat = create_exercise(db_session)
    start = datetime(2026, 11, 2, 18, 0, tzinfo=UTC)
    for days, weight in [(2, "105"), (0, "100"), (1, "102.5")]:
        create_set_record(
            db_session,
            user=user,
            exercise=squat,
            weight=Decimal(weight),
            performed_at=start + timedelta(days=days),
        )
    # Another user's and another exercise's records are left out
    create_set_record(db_session, exercise=squat)
    create_set_record(db_session, user=user)

    history = db_session.scalars(
        select(SetRecord.weight)
        .where(SetRecord.user_id == user.id, SetRecord.exercise_id == squat.id)
        .order_by(SetRecord.performed_at)
    ).all()

    assert history == [Decimal("100.00"), Decimal("102.50"), Decimal("105.00")]


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
