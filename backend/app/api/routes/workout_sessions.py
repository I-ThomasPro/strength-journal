import uuid

from fastapi import APIRouter, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.errors import ApiError
from app.api.pagination import PageQuery, paginate
from app.api.routine_parts import get_own_session, get_routine_workout, open_cycle
from app.api.visibility import require_owned
from app.auth.sessions import CurrentUser, now
from app.db import DbSession
from app.models.routine_workout import RoutineWorkout
from app.models.workout_session import WorkoutSession
from app.schemas.common import Page
from app.schemas.workout_session import (
    WorkoutSessionPut,
    WorkoutSessionRead,
    WorkoutSessionUpdate,
)

# Each time the user performs a workout: from a slot in one of their routines' cycles, or
# freestyle. Created with PUT and a client-generated id, so it can be made offline
router = APIRouter(tags=["workout-sessions"])

READ_OPTIONS = (
    joinedload(WorkoutSession.routine_workout),
    joinedload(WorkoutSession.workout),
    joinedload(WorkoutSession.cycle),
)


def usable_slot(db: Session, id: uuid.UUID, user_id: uuid.UUID) -> RoutineWorkout:
    """A slot in one of the user's own routines: 404 if they can't see it, 403 `read_only`
    for a library routine's (copy the routine first)"""
    slot = get_routine_workout(db, id, user_id)
    require_owned(slot.routine, user_id)
    return slot


def use_slot(db: Session, session: WorkoutSession, slot: RoutineWorkout | None) -> None:
    """Point the session at a slot (its workout, and its routine's open cycle), or make it
    freestyle. Re-sending the slot it already has changes nothing, so a retried request
    doesn't move an old session into a newer cycle"""
    if slot is not None and slot.id == session.routine_workout_id:
        return
    session.routine_workout = slot
    session.workout = slot.workout if slot else None
    session.cycle = open_cycle(db, slot.routine) if slot else None


def read(db: Session, session: WorkoutSession) -> WorkoutSessionRead:
    db.flush()
    db.refresh(session)
    return WorkoutSessionRead.model_validate(session)


@router.get("/workout-sessions")
def index(user: CurrentUser, db: DbSession, page: PageQuery) -> Page[WorkoutSessionRead]:
    """The user's sessions, newest first"""
    statement = (
        select(WorkoutSession)
        .where(WorkoutSession.user_id == user.id)
        .order_by(
            WorkoutSession.performed_at.desc(),
            WorkoutSession.created_at.desc(),
            WorkoutSession.id,
        )
        .options(*READ_OPTIONS)
    )
    sessions, total = paginate(db, statement, page)
    return Page(items=[WorkoutSessionRead.model_validate(s) for s in sessions], total=total)


@router.put("/workout-sessions/{id}")
def upsert(
    id: uuid.UUID, body: WorkoutSessionPut, user: CurrentUser, db: DbSession, response: Response
) -> WorkoutSessionRead:
    """Create a session under a client-generated id (201), or change the one with that id
    (200). On an existing session only the fields sent change, so the same request can be
    retried safely. 409 `id_conflict` if the id is another user's session"""
    session = db.get(WorkoutSession, id)
    if session is not None and session.user_id != user.id:
        raise ApiError(
            status.HTTP_409_CONFLICT, "id_conflict", "That id is already used; generate a new one"
        )
    sent = body.model_fields_set
    slot = None
    if body.routine_workout_id is not None:
        slot = usable_slot(db, body.routine_workout_id, user.id)
    if session is None:
        session = WorkoutSession(
            id=id,
            user_id=user.id,
            performed_at=body.performed_at if "performed_at" in sent else now(),
            completed=body.completed if "completed" in sent else False,
        )
        db.add(session)
        use_slot(db, session, slot)
        response.status_code = status.HTTP_201_CREATED
    else:
        if "routine_workout_id" in sent:
            use_slot(db, session, slot)
        if "performed_at" in sent:
            session.performed_at = body.performed_at
        if "completed" in sent:
            session.completed = body.completed
    return read(db, session)


@router.get("/workout-sessions/{id}")
def show(id: uuid.UUID, user: CurrentUser, db: DbSession) -> WorkoutSessionRead:
    return WorkoutSessionRead.model_validate(get_own_session(db, id, user.id))


@router.patch("/workout-sessions/{id}")
def update(
    id: uuid.UUID, body: WorkoutSessionUpdate, user: CurrentUser, db: DbSession
) -> WorkoutSessionRead:
    """Back-date the session, or mark it completed"""
    session = get_own_session(db, id, user.id)
    body.apply_to(session)
    return read(db, session)


@router.delete("/workout-sessions/{id}", status_code=status.HTTP_204_NO_CONTENT)
def destroy(id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    db.delete(get_own_session(db, id, user.id))
