import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlalchemy import func, select

from app.api.pagination import PageQuery, paginate
from app.api.visibility import Scope, get_visible_or_404, in_scope, require_owned
from app.auth.sessions import CurrentUser
from app.db import DbSession
from app.models.exercise import Exercise
from app.schemas.common import Page
from app.schemas.exercise import ExerciseCreate, ExerciseRead, ExerciseUpdate

# Library exercises (no owner) are read-only; users add and change their own
router = APIRouter(prefix="/exercises", tags=["exercises"])


@router.get("")
def index(
    user: CurrentUser,
    db: DbSession,
    page: PageQuery,
    scope: Scope = Scope.ALL,
    q: Annotated[
        str | None, Query(max_length=100, description="Part of the name, any case")
    ] = None,
) -> Page[ExerciseRead]:
    """Library exercises and the user's own, ordered by name"""
    statement = select(Exercise).where(in_scope(Exercise, scope, user.id))
    if q and q.strip():
        statement = statement.where(Exercise.name.icontains(q.strip(), autoescape=True))
    # Library first when a custom exercise has the same name
    statement = statement.order_by(
        func.lower(Exercise.name), Exercise.owner_id.nulls_first(), Exercise.id
    )
    exercises, total = paginate(db, statement, page)
    return Page(items=[ExerciseRead.model_validate(e) for e in exercises], total=total)


@router.post("", status_code=status.HTTP_201_CREATED)
def create(body: ExerciseCreate, user: CurrentUser, db: DbSession) -> ExerciseRead:
    """Add a custom exercise. 409 `duplicate_name` if the user already has one with this name,
    ignoring case; sharing a library exercise's name is fine"""
    exercise = Exercise(name=body.name, type=body.type, owner_id=user.id)
    db.add(exercise)
    db.flush()
    return ExerciseRead.model_validate(exercise)


@router.get("/{id}")
def show(id: uuid.UUID, user: CurrentUser, db: DbSession) -> ExerciseRead:
    return ExerciseRead.model_validate(get_visible_or_404(db, Exercise, id, user.id))


@router.patch("/{id}")
def update(id: uuid.UUID, body: ExerciseUpdate, user: CurrentUser, db: DbSession) -> ExerciseRead:
    """Change one of the user's exercises; 403 `read_only` for library exercises"""
    exercise = get_visible_or_404(db, Exercise, id, user.id)
    require_owned(exercise, user.id)
    body.apply_to(exercise)
    db.flush()
    return ExerciseRead.model_validate(exercise)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def destroy(id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    """Delete one of the user's exercises. 409 `exercise_in_use` if a workout or set record
    uses it; 403 `read_only` for library exercises"""
    exercise = get_visible_or_404(db, Exercise, id, user.id)
    require_owned(exercise, user.id)
    db.delete(exercise)
