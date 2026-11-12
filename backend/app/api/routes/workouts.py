import uuid

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.pagination import PageQuery, paginate
from app.api.routine_parts import get_workout
from app.api.visibility import get_visible_or_404, require_owned
from app.auth.sessions import CurrentUser
from app.db import DbSession
from app.models.ordering import renumber
from app.models.routine import Routine
from app.models.workout import Workout
from app.schemas.common import Page
from app.schemas.workout import WorkoutCreate, WorkoutRead, WorkoutUpdate

# A routine's workouts. Their order in the cycle is set by slots (routine-workouts). Only the
# user's own routines can be changed
router = APIRouter(tags=["workouts"])


@router.get("/routines/{routine_id}/workouts")
def index(
    routine_id: uuid.UUID, user: CurrentUser, db: DbSession, page: PageQuery
) -> Page[WorkoutRead]:
    """The routine's workouts, in the order they were added"""
    routine = get_visible_or_404(db, Routine, routine_id, user.id)
    statement = (
        select(Workout)
        .where(Workout.routine_id == routine.id)
        .order_by(Workout.created_at, Workout.id)
    )
    workouts, total = paginate(db, statement, page)
    return Page(items=[WorkoutRead.model_validate(workout) for workout in workouts], total=total)


@router.post("/routines/{routine_id}/workouts", status_code=status.HTTP_201_CREATED)
def create(
    routine_id: uuid.UUID, body: WorkoutCreate, user: CurrentUser, db: DbSession
) -> WorkoutRead:
    """Add a workout to the routine. It isn't in the cycle until a slot points at it"""
    routine = get_visible_or_404(db, Routine, routine_id, user.id)
    require_owned(routine, user.id)
    workout = Workout(routine=routine, name=body.name)
    db.add(workout)
    db.flush()
    return WorkoutRead.model_validate(workout)


@router.get("/workouts/{id}")
def show(id: uuid.UUID, user: CurrentUser, db: DbSession) -> WorkoutRead:
    return WorkoutRead.model_validate(get_workout(db, id, user.id))


@router.patch("/workouts/{id}")
def update(id: uuid.UUID, body: WorkoutUpdate, user: CurrentUser, db: DbSession) -> WorkoutRead:
    """Rename the workout"""
    workout = get_workout(db, id, user.id)
    require_owned(workout.routine, user.id)
    body.apply_to(workout)
    db.flush()
    return WorkoutRead.model_validate(workout)


@router.delete("/workouts/{id}", status_code=status.HTTP_204_NO_CONTENT)
def destroy(id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    """Delete the workout with its exercises and sets, and take its slots out of the cycle;
    the remaining slots close up"""
    workout = get_workout(db, id, user.id)
    routine = workout.routine
    require_owned(routine, user.id)
    # Slots left out of the collection are deleted as orphans
    routine.slots = renumber([slot for slot in routine.slots if slot.workout_id != workout.id])
    db.delete(workout)
