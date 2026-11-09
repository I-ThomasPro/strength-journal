import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.exercise import Exercise, ExerciseType
from tests.factories import create_exercise, create_user


def test_library_exercise_has_no_owner_and_defaults_to_strength(db_session: Session) -> None:
    exercise = create_exercise(db_session, name="Back Squat")
    db_session.refresh(exercise)

    assert exercise.owner_id is None
    assert exercise.owner is None
    assert exercise.type is ExerciseType.STRENGTH


def test_custom_exercise_belongs_to_its_owner(db_session: Session) -> None:
    user = create_user(db_session)
    exercise = create_exercise(db_session, name="Tempo Squat", owner=user)
    db_session.refresh(exercise)

    assert exercise.owner_id == user.id
    assert exercise.owner is user


@pytest.mark.parametrize("second_name", ["Bench Press", "bench press", "BENCH PRESS"])
def test_duplicate_library_name_is_rejected(db_session: Session, second_name: str) -> None:
    create_exercise(db_session, name="Bench Press")

    with pytest.raises(IntegrityError, match="uq_exercises_owner_id_lower_name"):
        create_exercise(db_session, name=second_name)


@pytest.mark.parametrize("second_name", ["Pause Bench", "pause bench"])
def test_duplicate_name_for_one_user_is_rejected(db_session: Session, second_name: str) -> None:
    user = create_user(db_session)
    create_exercise(db_session, name="Pause Bench", owner=user)

    with pytest.raises(IntegrityError, match="uq_exercises_owner_id_lower_name"):
        create_exercise(db_session, name=second_name, owner=user)


def test_same_name_is_allowed_for_different_users_and_the_library(db_session: Session) -> None:
    first, second = create_user(db_session), create_user(db_session)

    create_exercise(db_session, name="Deadlift")
    create_exercise(db_session, name="Deadlift", owner=first)
    create_exercise(db_session, name="deadlift", owner=second)

    names = db_session.scalars(select(Exercise.name).where(Exercise.name.ilike("deadlift")))
    assert len(names.all()) == 3


@pytest.mark.parametrize("exercise_type", ["cardio", "STRENGTH", ""])
def test_invalid_type_is_rejected(db_session: Session, exercise_type: str) -> None:
    with pytest.raises(IntegrityError, match="ck_exercises_type"):
        create_exercise(db_session, type=exercise_type)


def test_deleting_a_user_deletes_their_exercises_but_not_the_library(db_session: Session) -> None:
    user = create_user(db_session)
    library = create_exercise(db_session, name="Overhead Press")
    custom = create_exercise(db_session, name="Z Press", owner=user)
    library_id, custom_id = library.id, custom.id

    db_session.delete(user)
    db_session.flush()
    db_session.expunge_all()

    remaining = set(db_session.scalars(select(Exercise.id)))
    assert library_id in remaining
    assert custom_id not in remaining
