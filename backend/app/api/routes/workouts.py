import uuid

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.pagination import PageQuery, paginate
from app.api.routine_parts import get_workout, reorder
from app.api.visibility import get_visible_or_404, require_owned
from app.auth.sessions import CurrentUser
from app.db import DbSession
from app.models.ordering import place, remove
from app.models.routine import Routine
from app.models.workout import Workout
from app.schemas.common import Page
from app.schemas.workout import WorkoutCreate, WorkoutOrder, WorkoutRead, WorkoutUpdate

# A routine's workouts, in order. Only the user's own routines can be changed
router = APIRouter(tags=["workouts"])


def own_routine(db: DbSession, routine_id: uuid.UUID, user_id: uuid.UUID) -> Routine:
    routine = get_visible_or_404(db, Routine, routine_id, user_id)
    require_owned(routine, user_id)
    return routine


@router.get("/routines/{routine_id}/workouts")
def index(
    routine_id: uuid.UUID, user: CurrentUser, db: DbSession, page: PageQuery
) -> Page[WorkoutRead]:
    """The routine's workouts in position order"""
    routine = get_visible_or_404(db, Routine, routine_id, user.id)
    statement = select(Workout).where(Workout.routine_id == routine.id).order_by(Workout.position)
    workouts, total = paginate(db, statement, page)
    return Page(items=[WorkoutRead.model_validate(workout) for workout in workouts], total=total)


@router.post("/routines/{routine_id}/workouts", status_code=status.HTTP_201_CREATED)
def create(
    routine_id: uuid.UUID, body: WorkoutCreate, user: CurrentUser, db: DbSession
) -> WorkoutRead:
    """Add a workout at the end, or at `position`, shifting later ones"""
    routine = own_routine(db, routine_id, user.id)
    workout = Workout(name=body.name, position=0)
    routine.workouts = place(routine.workouts, workout, body.position)
    db.flush()
    return WorkoutRead.model_validate(workout)


@router.put("/routines/{routine_id}/workouts/order")
def order(
    routine_id: uuid.UUID, body: WorkoutOrder, user: CurrentUser, db: DbSession
) -> list[WorkoutRead]:
    """Set the order of all the routine's workouts at once; returns them in the new order"""
    routine = own_routine(db, routine_id, user.id)
    routine.workouts = reorder(routine.workouts, body.workout_ids, "routine's workouts")
    db.flush()
    return [WorkoutRead.model_validate(workout) for workout in routine.workouts]


@router.get("/workouts/{id}")
def show(id: uuid.UUID, user: CurrentUser, db: DbSession) -> WorkoutRead:
    return WorkoutRead.model_validate(get_workout(db, id, user.id))


@router.patch("/workouts/{id}")
def update(id: uuid.UUID, body: WorkoutUpdate, user: CurrentUser, db: DbSession) -> WorkoutRead:
    """Rename the workout, or move it with `position`"""
    workout = get_workout(db, id, user.id)
    routine = workout.routine
    require_owned(routine, user.id)
    body.apply_to(workout, exclude={"position"})
    if "position" in body.model_fields_set:
        routine.workouts = place(routine.workouts, workout, body.position)
    db.flush()
    return WorkoutRead.model_validate(workout)


@router.delete("/workouts/{id}", status_code=status.HTTP_204_NO_CONTENT)
def destroy(id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    """Delete the workout with its exercises and sets; later workouts move up"""
    workout = get_workout(db, id, user.id)
    routine = workout.routine
    require_owned(routine, user.id)
    routine.workouts = remove(routine.workouts, workout)
    db.delete(workout)
