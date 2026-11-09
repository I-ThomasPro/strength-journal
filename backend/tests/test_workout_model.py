import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.exercise import Exercise
from app.models.workout import Workout, WorkoutExercise
from tests.factories import (
    create_exercise,
    create_routine,
    create_workout,
    create_workout_exercise,
)


def check_deferred_constraints(session: Session) -> None:
    """Position uniqueness is checked at commit; force the check now (tests never commit)"""
    session.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def test_routine_workouts_are_ordered_by_position(db_session: Session) -> None:
    routine = create_routine(db_session)
    create_workout(db_session, routine, name="Day C", position=2)
    create_workout(db_session, routine, name="Day A", position=0)
    create_workout(db_session, routine, name="Day B", position=1)
    db_session.expire(routine)

    assert [workout.name for workout in routine.workouts] == ["Day A", "Day B", "Day C"]
    assert all(workout.routine is routine for workout in routine.workouts)


def test_duplicate_workout_position_in_a_routine_is_rejected(db_session: Session) -> None:
    routine = create_routine(db_session)
    create_workout(db_session, routine, position=0)
    create_workout(db_session, routine, position=0)

    with pytest.raises(IntegrityError, match="uq_workouts_routine_id_position"):
        check_deferred_constraints(db_session)


def test_same_workout_position_in_different_routines_is_allowed(db_session: Session) -> None:
    create_workout(db_session, create_routine(db_session), position=0)
    create_workout(db_session, create_routine(db_session), position=0)

    check_deferred_constraints(db_session)


def test_workout_positions_can_be_swapped_in_one_transaction(db_session: Session) -> None:
    routine = create_routine(db_session)
    first = create_workout(db_session, routine, name="Squat Day", position=0)
    second = create_workout(db_session, routine, name="Bench Day", position=1)

    first.position, second.position = 1, 0
    db_session.flush()
    check_deferred_constraints(db_session)
    db_session.expire(routine)

    assert [workout.name for workout in routine.workouts] == ["Bench Day", "Squat Day"]


def test_negative_workout_position_is_rejected(db_session: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_workouts_position_non_negative"):
        create_workout(db_session, position=-1)


def test_workout_exercises_are_ordered_by_position(db_session: Session) -> None:
    workout = create_workout(db_session)
    squat = create_exercise(db_session, name="Squat")
    bench = create_exercise(db_session, name="Bench")
    row = create_exercise(db_session, name="Row")
    create_workout_exercise(db_session, workout, row, position=2)
    create_workout_exercise(db_session, workout, squat, position=0)
    create_workout_exercise(db_session, workout, bench, position=1)
    db_session.expire(workout)

    assert [entry.exercise.name for entry in workout.exercises] == ["Squat", "Bench", "Row"]
    assert all(entry.workout is workout for entry in workout.exercises)


def test_duplicate_exercise_position_in_a_workout_is_rejected(db_session: Session) -> None:
    workout = create_workout(db_session)
    create_workout_exercise(db_session, workout, position=0)
    create_workout_exercise(db_session, workout, position=0)

    with pytest.raises(IntegrityError, match="uq_workout_exercises_workout_id_position"):
        check_deferred_constraints(db_session)


def test_negative_exercise_position_is_rejected(db_session: Session) -> None:
    with pytest.raises(IntegrityError, match="ck_workout_exercises_position_non_negative"):
        create_workout_exercise(db_session, position=-1)


def test_same_exercise_can_appear_in_several_workouts(db_session: Session) -> None:
    routine = create_routine(db_session)
    squat = create_exercise(db_session, name="Squat")
    day_a = create_workout(db_session, routine, name="Day A")
    day_b = create_workout(db_session, routine, name="Day B")
    create_workout_exercise(db_session, day_a, squat)
    create_workout_exercise(db_session, day_b, squat)

    check_deferred_constraints(db_session)
    uses = db_session.scalar(select(func.count()).where(WorkoutExercise.exercise_id == squat.id))
    assert uses == 2


def test_deleting_a_routine_deletes_its_workouts_and_their_exercises(db_session: Session) -> None:
    routine = create_routine(db_session)
    workout = create_workout(db_session, routine)
    entry = create_workout_exercise(db_session, workout)
    other_workout = create_workout(db_session)
    workout_id, entry_id, exercise_id = workout.id, entry.id, entry.exercise_id

    db_session.delete(routine)
    db_session.flush()
    db_session.expunge_all()

    assert db_session.get(Workout, workout_id) is None
    assert db_session.get(WorkoutExercise, entry_id) is None
    assert db_session.get(Workout, other_workout.id) is not None
    # The exercise itself is untouched
    assert db_session.get(Exercise, exercise_id) is not None


def test_removing_an_exercise_from_a_workout_deletes_that_entry(db_session: Session) -> None:
    workout = create_workout(db_session)
    entry = create_workout_exercise(db_session, workout)
    entry_id = entry.id
    db_session.expire(workout)

    workout.exercises.remove(entry)
    db_session.flush()

    assert db_session.get(WorkoutExercise, entry_id) is None


def test_deleting_an_exercise_in_use_is_rejected(db_session: Session) -> None:
    entry = create_workout_exercise(db_session)

    db_session.delete(entry.exercise)
    with pytest.raises(IntegrityError, match="fk_workout_exercises_exercise_id_exercises"):
        db_session.flush()
