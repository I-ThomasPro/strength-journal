import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from pydantic import AwareDatetime
from sqlalchemy import func, select
from sqlalchemy.orm import Session, contains_eager

from app.api.errors import ApiError, invalid, not_found
from app.api.pagination import MAX_LIMIT
from app.api.routine_parts import get_own_session, get_set, get_usable_exercise
from app.api.visibility import get_visible_or_404
from app.auth.sessions import CurrentUser
from app.db import DbSession
from app.models.common import WeightUnit
from app.models.exercise import Exercise
from app.models.ordering import place, remove
from app.models.set import Set
from app.models.set_record import SetRecord
from app.models.workout import WorkoutExercise
from app.models.workout_session import WorkoutSession
from app.schemas.common import NewForm, Page, enum_options
from app.schemas.set_record import SetRecordDefaults, SetRecordPut, SetRecordRead

# The sets a user actually did, each at a position in one of their workout sessions: logged
# with PUT and a client-generated id, so a retry after a dropped connection can't log a set
# twice, and read back as an exercise's history. A session's own list of records is in
# session_set_records.py
router = APIRouter(tags=["set-records"])

# History order: newest session first, then the session's records in order
NEWEST_FIRST = (WorkoutSession.performed_at.desc(), WorkoutSession.id.desc(), SetRecord.position)


def get_own_record(db: Session, id: uuid.UUID, user_id: uuid.UUID) -> SetRecord:
    record = db.get(SetRecord, id)
    if record is None or record.session.user_id != user_id:
        raise not_found()
    return record


def prescribed_set(db: Session, session: WorkoutSession, set_id: uuid.UUID) -> Set:
    """A set in the session's workout; 422 otherwise (a freestyle session has none)"""
    set_ = None
    if session.workout_id is not None:
        set_ = db.scalar(
            select(Set)
            .join(Set.workout_exercise)
            .where(Set.id == set_id, WorkoutExercise.workout_id == session.workout_id)
        )
    if set_ is None:
        raise invalid("That set isn't in this session's workout")
    return set_


def link(record: SetRecord, set_: Set | None) -> None:
    """Link the record to a prescribed set, copying its targets, or unlink it. Re-sending the
    set it's already linked to keeps the copy, so later target changes don't alter it"""
    if set_ is not None and set_.id == record.set_id:
        return
    record.set = set_
    record.target_reps = set_.target_reps if set_ else None
    record.target_weight = set_.target_weight if set_ else None
    record.target_unit = set_.weight_unit if set_ else None


@router.get("/exercises/{exercise_id}/set-records")
def index(
    exercise_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    since: Annotated[
        AwareDatetime | None, Query(description="Sessions from this time, inclusive")
    ] = None,
    until: Annotated[AwareDatetime | None, Query(description="Sessions before this time")] = None,
    before: Annotated[
        AwareDatetime | None,
        Query(description="The `performed_at` of the last record already shown; pages back"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
) -> Page[SetRecordRead]:
    """The user's history of the exercise: newest session first, then each session's records
    in order. Times are the sessions' `performed_at`. Page back by passing the last record's
    `performed_at` as `before`. A page runs past `limit` when needed so records with the
    same time are never split across pages. `total` counts every match"""
    exercise = get_visible_or_404(db, Exercise, exercise_id, user.id)
    filters = [WorkoutSession.user_id == user.id, SetRecord.exercise_id == exercise.id]
    if since is not None:
        filters.append(WorkoutSession.performed_at >= since)
    if until is not None:
        filters.append(WorkoutSession.performed_at < until)
    if before is not None:
        filters.append(WorkoutSession.performed_at < before)
    matching = (
        select(SetRecord)
        .join(SetRecord.session)
        .where(*filters)
        .options(contains_eager(SetRecord.session))
    )
    records = list(db.scalars(matching.order_by(*NEWEST_FIRST).limit(limit)))
    if len(records) == limit:
        # Finish the last time, so paging with `before` doesn't skip records sharing it
        shown = {record.id for record in records}
        last_time = records[-1].session.performed_at
        records += [
            record
            for record in db.scalars(
                matching.where(WorkoutSession.performed_at == last_time).order_by(*NEWEST_FIRST)
            )
            if record.id not in shown
        ]
    total = db.scalar(
        select(func.count()).select_from(SetRecord).join(SetRecord.session).where(*filters)
    )
    return Page(
        items=[SetRecordRead.model_validate(record) for record in records], total=total or 0
    )


@router.get("/exercises/{exercise_id}/set-records/new")
def new(
    exercise_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    set_id: Annotated[
        uuid.UUID | None, Query(description="A prescribed set of this exercise to start from")
    ] = None,
) -> NewForm[SetRecordDefaults]:
    """Suggested values for logging the exercise: the given set's targets, else the user's
    latest record of it, else just their preferred unit"""
    exercise = get_visible_or_404(db, Exercise, exercise_id, user.id)
    if set_id is not None:
        set_ = get_set(db, set_id, user.id)
        if set_.workout_exercise.exercise_id != exercise.id:
            raise invalid("That set is for a different exercise")
        defaults = SetRecordDefaults(
            reps=set_.target_reps, weight=set_.target_weight, weight_unit=set_.weight_unit
        )
    else:
        latest = db.scalar(
            select(SetRecord)
            .join(SetRecord.session)
            .where(WorkoutSession.user_id == user.id, SetRecord.exercise_id == exercise.id)
            .order_by(
                WorkoutSession.performed_at.desc(),
                WorkoutSession.id.desc(),
                SetRecord.position.desc(),
            )
            .limit(1)
        )
        defaults = SetRecordDefaults(
            reps=latest.reps if latest else None,
            weight=latest.weight if latest else None,
            weight_unit=latest.weight_unit if latest else user.weight_unit,
        )
    return NewForm(defaults=defaults, options=enum_options(weight_unit=WeightUnit))


@router.put("/set-records/{id}")
def upsert(
    id: uuid.UUID, body: SetRecordPut, user: CurrentUser, db: DbSession, response: Response
) -> SetRecordRead:
    """Log a set under a client-generated id, or replace the record with that id: 201 when
    created, 200 when replaced, so the same request can be retried safely. 409 `id_conflict`
    if the id is another user's record. The session must be the user's own (404), and the
    exercise a library one or the user's own, and `set_id` a set in the session's workout
    (422)"""
    record = db.get(SetRecord, id)
    if record is not None and record.session.user_id != user.id:
        raise ApiError(
            status.HTTP_409_CONFLICT, "id_conflict", "That id is already used; generate a new one"
        )
    session = get_own_session(db, body.session_id, user.id)
    exercise = get_usable_exercise(db, body.exercise_id, user.id)
    set_ = prescribed_set(db, session, body.set_id) if body.set_id is not None else None
    if record is None:
        record = SetRecord(id=id, position=0)
        session.set_records = place(session.set_records, record, body.position)
        response.status_code = status.HTTP_201_CREATED
    elif record.session_id != session.id:
        # Load the new session's records before the move, so a flush in between can't
        # delete the record as an orphan of its old session
        siblings = list(session.set_records)
        old = record.session
        old.set_records = remove(old.set_records, record)
        session.set_records = place(siblings, record, body.position)
    elif body.position is not None:
        session.set_records = place(session.set_records, record, body.position)
    link(record, set_)
    record.exercise = exercise
    record.reps = body.reps
    record.weight = body.weight
    record.weight_unit = body.weight_unit or user.weight_unit
    db.flush()
    return SetRecordRead.model_validate(record)


@router.get("/set-records/{id}")
def show(id: uuid.UUID, user: CurrentUser, db: DbSession) -> SetRecordRead:
    return SetRecordRead.model_validate(get_own_record(db, id, user.id))


@router.delete("/set-records/{id}", status_code=status.HTTP_204_NO_CONTENT)
def destroy(id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    """Delete the record; later records in its session move up"""
    record = get_own_record(db, id, user.id)
    session = record.session
    session.set_records = remove(session.set_records, record)
    db.delete(record)
