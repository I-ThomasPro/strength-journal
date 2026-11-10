import uuid

from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.api.pagination import PageQuery, paginate
from app.api.routine_parts import get_usable_exercise, get_workout, get_workout_exercise, reorder
from app.api.visibility import require_owned
from app.auth.sessions import CurrentUser
from app.db import DbSession
from app.models.ordering import place, remove
from app.models.workout import Workout, WorkoutExercise
from app.schemas.common import Page
from app.schemas.workout import (
    WorkoutExerciseCreate,
    WorkoutExerciseOrder,
    WorkoutExerciseRead,
    WorkoutExerciseUpdate,
)

# A workout's exercises, in order. Only the user's own routines can be changed
router = APIRouter(tags=["workout-exercises"])


def own_workout(db: DbSession, workout_id: uuid.UUID, user_id: uuid.UUID) -> Workout:
    workout = get_workout(db, workout_id, user_id)
    require_owned(workout.routine, user_id)
    return workout


@router.get("/workouts/{workout_id}/workout-exercises")
def index(
    workout_id: uuid.UUID, user: CurrentUser, db: DbSession, page: PageQuery
) -> Page[WorkoutExerciseRead]:
    """The workout's exercises in position order"""
    workout = get_workout(db, workout_id, user.id)
    statement = (
        select(WorkoutExercise)
        .where(WorkoutExercise.workout_id == workout.id)
        .order_by(WorkoutExercise.position)
        .options(joinedload(WorkoutExercise.exercise))
    )
    entries, total = paginate(db, statement, page)
    return Page(items=[WorkoutExerciseRead.model_validate(e) for e in entries], total=total)


@router.post("/workouts/{workout_id}/workout-exercises", status_code=status.HTTP_201_CREATED)
def create(
    workout_id: uuid.UUID, body: WorkoutExerciseCreate, user: CurrentUser, db: DbSession
) -> WorkoutExerciseRead:
    """Add an exercise at the end, or at `position`. 422 unless it's a library exercise or
    one of the user's own"""
    workout = own_workout(db, workout_id, user.id)
    exercise = get_usable_exercise(db, body.exercise_id, user.id)
    entry = WorkoutExercise(exercise=exercise, position=0)
    workout.exercises = place(workout.exercises, entry, body.position)
    db.flush()
    return WorkoutExerciseRead.model_validate(entry)


@router.put("/workouts/{workout_id}/workout-exercises/order")
def order(
    workout_id: uuid.UUID, body: WorkoutExerciseOrder, user: CurrentUser, db: DbSession
) -> list[WorkoutExerciseRead]:
    """Set the order of all the workout's exercises at once; returns them in the new order"""
    workout = own_workout(db, workout_id, user.id)
    workout.exercises = reorder(workout.exercises, body.workout_exercise_ids, "workout's exercises")
    db.flush()
    return [WorkoutExerciseRead.model_validate(entry) for entry in workout.exercises]


@router.get("/workout-exercises/{id}")
def show(id: uuid.UUID, user: CurrentUser, db: DbSession) -> WorkoutExerciseRead:
    return WorkoutExerciseRead.model_validate(get_workout_exercise(db, id, user.id))


@router.patch("/workout-exercises/{id}")
def update(
    id: uuid.UUID, body: WorkoutExerciseUpdate, user: CurrentUser, db: DbSession
) -> WorkoutExerciseRead:
    """Swap in a different exercise (keeping the sets), or move it with `position`"""
    entry = get_workout_exercise(db, id, user.id)
    workout = entry.workout
    require_owned(workout.routine, user.id)
    if "exercise_id" in body.model_fields_set:
        entry.exercise = get_usable_exercise(db, body.exercise_id, user.id)
    if "position" in body.model_fields_set:
        workout.exercises = place(workout.exercises, entry, body.position)
    db.flush()
    return WorkoutExerciseRead.model_validate(entry)


@router.delete("/workout-exercises/{id}", status_code=status.HTTP_204_NO_CONTENT)
def destroy(id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    """Delete it with its sets; later exercises move up"""
    entry = get_workout_exercise(db, id, user.id)
    workout = entry.workout
    require_owned(workout.routine, user.id)
    workout.exercises = remove(workout.exercises, entry)
    db.delete(entry)
