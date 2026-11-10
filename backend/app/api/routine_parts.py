"""Loading a routine's parts (workouts, workout exercises) under the routine's visibility rules

- Reading follows the routine: library routines' parts and the user's own
- Changing needs the user's own routine: pass the routine to `require_owned()`, which gives
  403 `read_only` for library routines and 404 for another user's
"""

import uuid
from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import invalid, not_found
from app.api.visibility import visible_to
from app.models.exercise import Exercise
from app.models.ordering import renumber
from app.models.routine import Routine
from app.models.workout import Workout, WorkoutExercise


def get_workout(db: Session, id: uuid.UUID, user_id: uuid.UUID) -> Workout:
    """A workout in a routine the user can see; 404 otherwise"""
    workout = db.scalar(
        select(Workout).join(Workout.routine).where(Workout.id == id, visible_to(Routine, user_id))
    )
    if workout is None:
        raise not_found()
    return workout


def get_workout_exercise(db: Session, id: uuid.UUID, user_id: uuid.UUID) -> WorkoutExercise:
    """A workout exercise in a routine the user can see; 404 otherwise"""
    workout_exercise = db.scalar(
        select(WorkoutExercise)
        .join(WorkoutExercise.workout)
        .join(Workout.routine)
        .where(WorkoutExercise.id == id, visible_to(Routine, user_id))
    )
    if workout_exercise is None:
        raise not_found()
    return workout_exercise


def get_usable_exercise(db: Session, id: uuid.UUID, user_id: uuid.UUID) -> Exercise:
    """An exercise the user can add: a library exercise or their own. 422 otherwise, since
    it's a reference in the request body rather than the resource being asked for"""
    exercise = db.scalar(select(Exercise).where(Exercise.id == id, visible_to(Exercise, user_id)))
    if exercise is None:
        raise invalid("There's no such exercise")
    return exercise


class Ordered(Protocol):
    id: uuid.UUID
    position: int


def reorder[O: Ordered](siblings: Sequence[O], ids: list[uuid.UUID], siblings_name: str) -> list[O]:
    """Put every sibling in the order of `ids`, renumbering them from 0. 422 unless `ids`
    lists each sibling exactly once"""
    by_id = {sibling.id: sibling for sibling in siblings}
    if len(ids) != len(set(ids)) or set(ids) != set(by_id):
        raise invalid(f"List each of the {siblings_name} exactly once")
    return renumber([by_id[id] for id in ids])
