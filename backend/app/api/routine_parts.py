"""Loading a routine's parts (slots, workouts, workout exercises, sets) by its visibility

- Reading follows the routine: library routines' parts and the user's own
- Changing needs the user's own routine: pass the routine to `require_owned()`, which gives
  403 `read_only` for library routines and 404 for another user's
"""

import uuid
from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.errors import invalid, not_found
from app.api.visibility import visible_to
from app.models.exercise import Exercise
from app.models.ordering import renumber
from app.models.routine import Routine
from app.models.routine_cycle import RoutineCycle
from app.models.routine_workout import RoutineWorkout
from app.models.set import Set
from app.models.workout import Workout, WorkoutExercise
from app.models.workout_session import WorkoutSession


def current_cycle(db: Session, routine: Routine) -> RoutineCycle | None:
    """The routine's open cycle, if it has one"""
    return db.scalar(
        select(RoutineCycle).where(
            RoutineCycle.routine_id == routine.id, RoutineCycle.completed_at.is_(None)
        )
    )


def open_cycle(db: Session, routine: Routine) -> RoutineCycle:
    """The routine's open cycle, opening the next one (1 for a new routine) if it has none"""
    cycle = current_cycle(db, routine)
    if cycle is None:
        last = db.scalar(
            select(func.max(RoutineCycle.number)).where(RoutineCycle.routine_id == routine.id)
        )
        cycle = RoutineCycle(routine_id=routine.id, number=(last or 0) + 1)
        db.add(cycle)
        db.flush()
    return cycle


def next_slot(
    db: Session, routine: Routine, cycle: RoutineCycle | None, user_id: uuid.UUID
) -> RoutineWorkout | None:
    """The slot to do next in the cycle: the one after the user's latest completed session
    (by performed_at), the first if none is completed, or None once the last slot is done"""
    slots = routine.slots
    latest = None
    if cycle is not None:
        latest = db.scalar(
            select(RoutineWorkout)
            .join(WorkoutSession, WorkoutSession.routine_workout_id == RoutineWorkout.id)
            .where(
                WorkoutSession.cycle_id == cycle.id,
                WorkoutSession.user_id == user_id,
                WorkoutSession.completed.is_(True),
            )
            .order_by(WorkoutSession.performed_at.desc(), WorkoutSession.created_at.desc())
            .limit(1)
        )
    if latest is None:
        return slots[0] if slots else None
    return next((slot for slot in slots if slot.position > latest.position), None)


def get_own_session(db: Session, id: uuid.UUID, user_id: uuid.UUID) -> WorkoutSession:
    """One of the user's workout sessions; 404 otherwise"""
    session = db.get(WorkoutSession, id)
    if session is None or session.user_id != user_id:
        raise not_found()
    return session


def get_routine_workout(db: Session, id: uuid.UUID, user_id: uuid.UUID) -> RoutineWorkout:
    """A slot in a routine the user can see; 404 otherwise"""
    slot = db.scalar(
        select(RoutineWorkout)
        .join(RoutineWorkout.routine)
        .where(RoutineWorkout.id == id, visible_to(Routine, user_id))
    )
    if slot is None:
        raise not_found()
    return slot


def get_routine_workout_target(db: Session, routine: Routine, workout_id: uuid.UUID) -> Workout:
    """The routine's own workout with this id, for a slot to point at. 422 otherwise, since
    it's a reference in the request body rather than the resource being asked for"""
    workout = db.scalar(
        select(Workout).where(Workout.id == workout_id, Workout.routine_id == routine.id)
    )
    if workout is None:
        raise invalid("That workout isn't in this routine")
    return workout


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


def get_set(db: Session, id: uuid.UUID, user_id: uuid.UUID) -> Set:
    """A set in a routine the user can see; 404 otherwise"""
    set_ = db.scalar(
        select(Set)
        .join(Set.workout_exercise)
        .join(WorkoutExercise.workout)
        .join(Workout.routine)
        .where(Set.id == id, visible_to(Routine, user_id))
    )
    if set_ is None:
        raise not_found()
    return set_


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
