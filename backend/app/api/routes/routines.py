import uuid
from datetime import timedelta

from fastapi import APIRouter, status
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from app.api.errors import not_found
from app.api.pagination import PageQuery, paginate
from app.api.routine_parts import current_cycle, next_slot, open_cycle
from app.api.visibility import Scope, get_visible_or_404, in_scope, require_owned, visible_to
from app.auth.sessions import CurrentUser
from app.db import DbSession
from app.models.routine import Routine
from app.models.routine_workout import RoutineWorkout
from app.models.set import Set
from app.models.workout import Workout, WorkoutExercise
from app.schemas.common import Page
from app.schemas.routine import (
    RoutineCopy,
    RoutineCreate,
    RoutineDetail,
    RoutineFields,
    RoutineSummary,
    RoutineUpdate,
)
from app.schemas.routine_cycle import RoutineCycleRead
from app.schemas.routine_workout import RoutineWorkoutRead

# Library routines (no owner) are read-only; users create and change their own, or copy one
router = APIRouter(prefix="/routines", tags=["routines"])

# Everything the detail shows, loaded in one query per level whatever the routine's size
DETAIL_OPTIONS = (
    selectinload(Routine.workouts)
    .selectinload(Workout.exercises)
    .options(joinedload(WorkoutExercise.exercise), selectinload(WorkoutExercise.sets)),
    selectinload(Routine.slots).joinedload(RoutineWorkout.workout),
)


def detail(db: DbSession, routine: Routine, user_id: uuid.UUID) -> RoutineDetail:
    """The routine with everything RoutineDetail shows, including the user's next slot in the
    current cycle"""
    cycle = current_cycle(db, routine)
    slot = next_slot(db, routine, cycle, user_id)
    return RoutineDetail.model_validate(routine).model_copy(
        update={
            "current_cycle": RoutineCycleRead.model_validate(cycle) if cycle else None,
            "next_slot": RoutineWorkoutRead.model_validate(slot) if slot else None,
        }
    )


@router.get("")
def index(
    user: CurrentUser, db: DbSession, page: PageQuery, scope: Scope = Scope.ALL
) -> Page[RoutineSummary]:
    """Library routines and the user's own, ordered by name"""
    statement = (
        select(Routine)
        .where(in_scope(Routine, scope, user.id))
        .order_by(func.lower(Routine.name), Routine.owner_id.nulls_first(), Routine.id)
    )
    routines, total = paginate(db, statement, page)
    counts: dict[uuid.UUID, int] = {
        routine_id: workouts
        for routine_id, workouts in db.execute(
            select(Workout.routine_id, func.count())
            .where(Workout.routine_id.in_([routine.id for routine in routines]))
            .group_by(Workout.routine_id)
        )
    }
    items = [
        RoutineSummary(
            **RoutineFields.model_validate(routine).model_dump(),
            workout_count=counts.get(routine.id, 0),
        )
        for routine in routines
    ]
    return Page(items=items, total=total)


@router.post("", status_code=status.HTTP_201_CREATED)
def create(body: RoutineCreate, user: CurrentUser, db: DbSession) -> RoutineDetail:
    """Create an empty routine owned by the user, starting at cycle 1"""
    routine = Routine(name=body.name, description=body.description, owner_id=user.id)
    db.add(routine)
    db.flush()
    open_cycle(db, routine)
    return detail(db, routine, user.id)


@router.get("/{id}")
def show(id: uuid.UUID, user: CurrentUser, db: DbSession) -> RoutineDetail:
    """The whole routine: its workouts with their exercises and sets, and its cycle of slots"""
    routine = db.scalar(
        select(Routine)
        .where(Routine.id == id, visible_to(Routine, user.id))
        .options(*DETAIL_OPTIONS)
    )
    if routine is None:
        raise not_found()
    return detail(db, routine, user.id)


@router.post("/{id}/copy", status_code=status.HTTP_201_CREATED)
def copy(id: uuid.UUID, body: RoutineCopy, user: CurrentUser, db: DbSession) -> RoutineDetail:
    """Copy a library routine or one of the user's own into a new routine the user owns:
    its workouts, their exercises and sets, and its cycle of slots, keeping every position.
    Exercises are referenced, not copied"""
    source = db.scalar(
        select(Routine)
        .where(Routine.id == id, visible_to(Routine, user.id))
        .options(*DETAIL_OPTIONS)
    )
    if source is None:
        raise not_found()
    routine = Routine(
        owner_id=user.id,
        source_routine_id=source.id,
        name=body.name or source.name,
        description=(
            body.description if "description" in body.model_fields_set else source.description
        ),
    )
    copies: dict[uuid.UUID, Workout] = {}
    # Workouts are listed by created_at. Copies made in one transaction would all share it,
    # so step each one by a microsecond to keep the source's order
    copied_at = db.scalar(select(func.now()))
    for index, workout in enumerate(source.workouts):
        workout_copy = Workout(
            name=workout.name, created_at=copied_at + timedelta(microseconds=index)
        )
        copies[workout.id] = workout_copy
        routine.workouts.append(workout_copy)
        for entry in workout.exercises:
            entry_copy = WorkoutExercise(exercise_id=entry.exercise_id, position=entry.position)
            workout_copy.exercises.append(entry_copy)
            entry_copy.sets.extend(
                Set(
                    position=set_.position,
                    target_reps=set_.target_reps,
                    target_weight=set_.target_weight,
                    weight_unit=set_.weight_unit,
                )
                for set_ in entry.sets
            )
    routine.slots.extend(
        RoutineWorkout(workout=copies[slot.workout_id], position=slot.position)
        for slot in source.slots
    )
    db.add(routine)
    db.flush()
    open_cycle(db, routine)
    # Load the copy afresh, as `show` would
    db.expire_all()
    return show(routine.id, user, db)


@router.patch("/{id}")
def update(id: uuid.UUID, body: RoutineUpdate, user: CurrentUser, db: DbSession) -> RoutineDetail:
    """Rename one of the user's routines or change its description; 403 `read_only` for
    library routines"""
    routine = get_visible_or_404(db, Routine, id, user.id)
    require_owned(routine, user.id)
    body.apply_to(routine)
    db.flush()
    return show(id, user, db)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def destroy(id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    """Delete one of the user's routines, with its workouts and sets. Exercises and recorded
    sets stay; 403 `read_only` for library routines"""
    routine = get_visible_or_404(db, Routine, id, user.id)
    require_owned(routine, user.id)
    db.delete(routine)
