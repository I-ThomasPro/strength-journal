import uuid

from fastapi import APIRouter, status
from sqlalchemy import exists, select
from sqlalchemy.orm import Session, joinedload

from app.api.errors import invalid, not_found
from app.api.pagination import PageQuery, paginate
from app.api.visibility import get_visible_or_404, require_owned, visible_to
from app.auth.sessions import CurrentUser
from app.db import DbSession
from app.models.progression import Progression
from app.models.routine import Routine
from app.models.workout import Workout, WorkoutExercise
from app.schemas.common import Page
from app.schemas.progression import ProgressionCreate, ProgressionRead, ProgressionUpdate

# How a routine's exercises gain weight. Only the user's own routines can be changed
router = APIRouter(tags=["progressions"])


def get_progression(db: Session, id: uuid.UUID, user_id: uuid.UUID) -> Progression:
    """A progression in a routine the user can see; 404 otherwise"""
    progression = db.scalar(
        select(Progression)
        .join(Progression.routine)
        .where(Progression.id == id, visible_to(Routine, user_id))
    )
    if progression is None:
        raise not_found()
    return progression


def used_in_routine(db: Session, routine: Routine, exercise_id: uuid.UUID) -> bool:
    return bool(
        db.scalar(
            select(
                exists()
                .where(WorkoutExercise.exercise_id == exercise_id)
                .where(WorkoutExercise.workout_id == Workout.id)
                .where(Workout.routine_id == routine.id)
            )
        )
    )


@router.get("/routines/{routine_id}/progressions")
def index(
    routine_id: uuid.UUID, user: CurrentUser, db: DbSession, page: PageQuery
) -> Page[ProgressionRead]:
    """The routine's progressions, oldest first"""
    routine = get_visible_or_404(db, Routine, routine_id, user.id)
    statement = (
        select(Progression)
        .where(Progression.routine_id == routine.id)
        .order_by(Progression.created_at, Progression.id)
        .options(joinedload(Progression.exercise))
    )
    progressions, total = paginate(db, statement, page)
    return Page(items=[ProgressionRead.model_validate(p) for p in progressions], total=total)


@router.post("/routines/{routine_id}/progressions", status_code=status.HTTP_201_CREATED)
def create(
    routine_id: uuid.UUID, body: ProgressionCreate, user: CurrentUser, db: DbSession
) -> ProgressionRead:
    """Add a progression for an exercise in the routine's workouts. 409
    `duplicate_progression` if the routine already has one for it"""
    routine = get_visible_or_404(db, Routine, routine_id, user.id)
    require_owned(routine, user.id)
    if not used_in_routine(db, routine, body.exercise_id):
        raise invalid("That exercise isn't in any of the routine's workouts")
    progression = Progression(
        routine=routine,
        exercise_id=body.exercise_id,
        increment=body.increment,
        increment_unit=body.increment_unit or user.weight_unit,
        condition=body.condition,
    )
    db.add(progression)
    db.flush()
    return ProgressionRead.model_validate(progression)


@router.get("/progressions/{id}")
def show(id: uuid.UUID, user: CurrentUser, db: DbSession) -> ProgressionRead:
    return ProgressionRead.model_validate(get_progression(db, id, user.id))


@router.patch("/progressions/{id}")
def update(
    id: uuid.UUID, body: ProgressionUpdate, user: CurrentUser, db: DbSession
) -> ProgressionRead:
    """Change the increment, its unit or the condition"""
    progression = get_progression(db, id, user.id)
    require_owned(progression.routine, user.id)
    body.apply_to(progression)
    db.flush()
    return ProgressionRead.model_validate(progression)


@router.delete("/progressions/{id}", status_code=status.HTTP_204_NO_CONTENT)
def destroy(id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    progression = get_progression(db, id, user.id)
    require_owned(progression.routine, user.id)
    db.delete(progression)
