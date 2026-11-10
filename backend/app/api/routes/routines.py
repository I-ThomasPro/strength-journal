import uuid

from fastapi import APIRouter, status
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from app.api.errors import not_found
from app.api.pagination import PageQuery, paginate
from app.api.visibility import Scope, get_visible_or_404, in_scope, require_owned, visible_to
from app.auth.sessions import CurrentUser
from app.db import DbSession
from app.models.progression import Progression
from app.models.routine import Routine
from app.models.workout import Workout, WorkoutExercise
from app.schemas.common import Page
from app.schemas.routine import (
    RoutineCreate,
    RoutineDetail,
    RoutineFields,
    RoutineSummary,
    RoutineUpdate,
)

# Library routines (no owner) are read-only; users create and change their own.
# Copying a routine is a separate route
router = APIRouter(prefix="/routines", tags=["routines"])

# Everything the detail shows, loaded in one query per level whatever the routine's size
DETAIL_OPTIONS = (
    selectinload(Routine.workouts)
    .selectinload(Workout.exercises)
    .options(joinedload(WorkoutExercise.exercise), selectinload(WorkoutExercise.sets)),
    selectinload(Routine.progressions).joinedload(Progression.exercise),
)


def detail(routine: Routine) -> RoutineDetail:
    return RoutineDetail.model_validate(routine)


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
    """Create an empty routine owned by the user"""
    routine = Routine(name=body.name, description=body.description, owner_id=user.id)
    db.add(routine)
    db.flush()
    return detail(routine)


@router.get("/{id}")
def show(id: uuid.UUID, user: CurrentUser, db: DbSession) -> RoutineDetail:
    """The whole routine: its workouts, their exercises and sets, and its progressions"""
    routine = db.scalar(
        select(Routine)
        .where(Routine.id == id, visible_to(Routine, user.id))
        .options(*DETAIL_OPTIONS)
    )
    if routine is None:
        raise not_found()
    return detail(routine)


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
    """Delete one of the user's routines, with its workouts, sets and progressions. Exercises
    and recorded sets stay; 403 `read_only` for library routines"""
    routine = get_visible_or_404(db, Routine, id, user.id)
    require_owned(routine, user.id)
    db.delete(routine)
