"""Deleting a user removes everything they own, even when their records reference each other"""

from sqlalchemy.orm import Session

from app.models.exercise import Exercise
from app.models.set import Set
from app.models.workout import Workout, WorkoutExercise
from tests.factories import (
    create_exercise,
    create_routine,
    create_set,
    create_user,
    create_workout,
    create_workout_exercise,
)
from tests.helpers import check_deferred_constraints


def test_deleting_a_user_whose_workout_uses_their_custom_exercise(db_session: Session) -> None:
    user = create_user(db_session)
    exercise = create_exercise(db_session, owner=user)
    workout = create_workout(db_session, create_routine(db_session, owner=user))
    entry = create_workout_exercise(db_session, workout, exercise)
    set_ = create_set(db_session, entry)
    ids = {
        Exercise: exercise.id,
        Workout: workout.id,
        WorkoutExercise: entry.id,
        Set: set_.id,
    }

    db_session.delete(user)
    db_session.flush()
    check_deferred_constraints(db_session)
    db_session.expunge_all()

    assert all(db_session.get(model, id_) is None for model, id_ in ids.items())


def test_deleting_a_user_keeps_library_exercises_used_in_their_routines(
    db_session: Session,
) -> None:
    user = create_user(db_session)
    library_exercise = create_exercise(db_session)
    routine = create_routine(db_session, owner=user)
    create_workout_exercise(db_session, create_workout(db_session, routine), library_exercise)
    library_exercise_id = library_exercise.id

    db_session.delete(user)
    db_session.flush()
    check_deferred_constraints(db_session)
    db_session.expunge_all()

    assert db_session.get(Exercise, library_exercise_id) is not None
