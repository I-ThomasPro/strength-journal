import uuid

from fastapi import APIRouter, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.api.pagination import PageQuery, paginate
from app.api.routine_parts import get_routine_workout, get_routine_workout_target, reorder
from app.api.visibility import get_visible_or_404, require_owned
from app.auth.sessions import CurrentUser
from app.db import DbSession
from app.models.ordering import place, remove
from app.models.routine import Routine
from app.models.routine_workout import RoutineWorkout
from app.schemas.common import Page
from app.schemas.routine_workout import (
    RoutineWorkoutCreate,
    RoutineWorkoutOrder,
    RoutineWorkoutRead,
    RoutineWorkoutUpdate,
)

# A routine's cycle: slots saying which of its workouts comes at each position. A workout can
# fill several slots. Only the user's own routines can be changed
router = APIRouter(tags=["routine-workouts"])


def own_routine(db: DbSession, routine_id: uuid.UUID, user_id: uuid.UUID) -> Routine:
    routine = get_visible_or_404(db, Routine, routine_id, user_id)
    require_owned(routine, user_id)
    return routine


@router.get("/routines/{routine_id}/routine-workouts")
def index(
    routine_id: uuid.UUID, user: CurrentUser, db: DbSession, page: PageQuery
) -> Page[RoutineWorkoutRead]:
    """The routine's cycle, in position order"""
    routine = get_visible_or_404(db, Routine, routine_id, user.id)
    statement = (
        select(RoutineWorkout)
        .where(RoutineWorkout.routine_id == routine.id)
        .order_by(RoutineWorkout.position)
        .options(joinedload(RoutineWorkout.workout))
    )
    slots, total = paginate(db, statement, page)
    return Page(items=[RoutineWorkoutRead.model_validate(slot) for slot in slots], total=total)


@router.post("/routines/{routine_id}/routine-workouts", status_code=status.HTTP_201_CREATED)
def create(
    routine_id: uuid.UUID, body: RoutineWorkoutCreate, user: CurrentUser, db: DbSession
) -> RoutineWorkoutRead:
    """Add one of the routine's workouts to its cycle, at the end or at `position`, shifting
    later slots. 422 unless the workout is in this routine"""
    routine = own_routine(db, routine_id, user.id)
    workout = get_routine_workout_target(db, routine, body.workout_id)
    slot = RoutineWorkout(workout=workout, position=0)
    routine.slots = place(routine.slots, slot, body.position)
    db.flush()
    return RoutineWorkoutRead.model_validate(slot)


@router.put("/routines/{routine_id}/routine-workouts/order")
def order(
    routine_id: uuid.UUID, body: RoutineWorkoutOrder, user: CurrentUser, db: DbSession
) -> list[RoutineWorkoutRead]:
    """Set the order of all the routine's slots at once; returns them in the new order"""
    routine = own_routine(db, routine_id, user.id)
    routine.slots = reorder(routine.slots, body.routine_workout_ids, "routine's slots")
    db.flush()
    return [RoutineWorkoutRead.model_validate(slot) for slot in routine.slots]


@router.get("/routine-workouts/{id}")
def show(id: uuid.UUID, user: CurrentUser, db: DbSession) -> RoutineWorkoutRead:
    return RoutineWorkoutRead.model_validate(get_routine_workout(db, id, user.id))


@router.patch("/routine-workouts/{id}")
def update(
    id: uuid.UUID, body: RoutineWorkoutUpdate, user: CurrentUser, db: DbSession
) -> RoutineWorkoutRead:
    """Put a different one of the routine's workouts in the slot, or move it with `position`"""
    slot = get_routine_workout(db, id, user.id)
    routine = slot.routine
    require_owned(routine, user.id)
    if "workout_id" in body.model_fields_set:
        slot.workout = get_routine_workout_target(db, routine, body.workout_id)
    if "position" in body.model_fields_set:
        routine.slots = place(routine.slots, slot, body.position)
    db.flush()
    return RoutineWorkoutRead.model_validate(slot)


@router.delete("/routine-workouts/{id}", status_code=status.HTTP_204_NO_CONTENT)
def destroy(id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    """Take the slot out of the cycle; later slots move up. The workout itself stays"""
    slot = get_routine_workout(db, id, user.id)
    routine = slot.routine
    require_owned(routine, user.id)
    routine.slots = remove(routine.slots, slot)
    db.delete(slot)
