"""Simple model factories: build a valid record, override any field, add it and flush"""

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.common import WeightUnit
from app.models.exercise import Exercise
from app.models.routine import Routine
from app.models.routine_workout import RoutineWorkout
from app.models.set import Set
from app.models.set_record import SetRecord
from app.models.user import User
from app.models.workout import Workout, WorkoutExercise


def create_user(session: Session, **overrides: object) -> User:
    unique = uuid.uuid4().hex[:12]
    fields: dict[str, object] = {
        "email": f"user-{unique}@example.com",
        "password_hash": "not-a-real-hash",
        "display_name": f"User {unique}",
    }
    user = User(**(fields | overrides))
    session.add(user)
    session.flush()
    return user


def create_exercise(session: Session, **overrides: object) -> Exercise:
    """A shared library exercise unless `owner` or `owner_id` is given"""
    fields: dict[str, object] = {"name": f"Exercise {uuid.uuid4().hex[:12]}"}
    exercise = Exercise(**(fields | overrides))
    session.add(exercise)
    session.flush()
    return exercise


def create_routine(session: Session, **overrides: object) -> Routine:
    """A shared library routine unless `owner` or `owner_id` is given"""
    fields: dict[str, object] = {"name": f"Routine {uuid.uuid4().hex[:12]}"}
    routine = Routine(**(fields | overrides))
    session.add(routine)
    session.flush()
    return routine


def create_workout(
    session: Session, routine: Routine | None = None, **overrides: object
) -> Workout:
    """A workout in `routine` (a new library routine if not given), in no slot of its cycle"""
    routine = routine or create_routine(session)
    fields: dict[str, object] = {"routine": routine, "name": f"Workout {uuid.uuid4().hex[:12]}"}
    workout = Workout(**(fields | overrides))
    session.add(workout)
    session.flush()
    return workout


def create_routine_workout(
    session: Session, workout: Workout | None = None, **overrides: object
) -> RoutineWorkout:
    """A slot for `workout` (a new one if not given) at the end of its routine's cycle"""
    workout = workout or create_workout(session)
    next_position = session.scalar(
        select(func.count())
        .select_from(RoutineWorkout)
        .where(RoutineWorkout.routine_id == workout.routine_id)
    )
    fields: dict[str, object] = {
        "routine_id": workout.routine_id,
        "workout": workout,
        "position": next_position,
    }
    slot = RoutineWorkout(**(fields | overrides))
    session.add(slot)
    session.flush()
    return slot


def create_workout_exercise(
    session: Session,
    workout: Workout | None = None,
    exercise: Exercise | None = None,
    **overrides: object,
) -> WorkoutExercise:
    """`exercise` (a new library exercise if not given) appended to `workout` (or a new one)"""
    workout = workout or create_workout(session)
    exercise = exercise or create_exercise(session)
    next_position = session.scalar(
        select(func.count())
        .select_from(WorkoutExercise)
        .where(WorkoutExercise.workout_id == workout.id)
    )
    fields: dict[str, object] = {
        "workout": workout,
        "exercise": exercise,
        "position": next_position,
    }
    workout_exercise = WorkoutExercise(**(fields | overrides))
    session.add(workout_exercise)
    session.flush()
    return workout_exercise


def create_set(
    session: Session, workout_exercise: WorkoutExercise | None = None, **overrides: object
) -> Set:
    """5 reps at 60 kg, appended to `workout_exercise` (or a new one)"""
    workout_exercise = workout_exercise or create_workout_exercise(session)
    next_position = session.scalar(
        select(func.count()).select_from(Set).where(Set.workout_exercise_id == workout_exercise.id)
    )
    fields: dict[str, object] = {
        "workout_exercise": workout_exercise,
        "position": next_position,
        "target_reps": 5,
        "target_weight": Decimal("60"),
        "weight_unit": WeightUnit.KG,
    }
    set_ = Set(**(fields | overrides))
    session.add(set_)
    session.flush()
    return set_


def create_set_record(session: Session, **overrides: object) -> SetRecord:
    """5 reps at 60 kg by a new user, of a new library exercise, unless given"""
    fields: dict[str, object] = {
        "reps": 5,
        "weight": Decimal("60"),
        "weight_unit": WeightUnit.KG,
    }
    if "user" not in overrides and "user_id" not in overrides:
        fields["user"] = create_user(session)
    if "exercise" not in overrides and "exercise_id" not in overrides:
        fields["exercise"] = create_exercise(session)
    set_record = SetRecord(**(fields | overrides))
    session.add(set_record)
    session.flush()
    return set_record
