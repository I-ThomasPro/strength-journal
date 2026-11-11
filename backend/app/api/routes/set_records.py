import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from pydantic import AwareDatetime
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.errors import ApiError, not_found
from app.api.pagination import MAX_LIMIT
from app.api.routine_parts import get_usable_exercise
from app.api.visibility import get_visible_or_404
from app.auth.sessions import CurrentUser, now
from app.db import DbSession
from app.models.common import WeightUnit
from app.models.exercise import Exercise
from app.models.set_record import SetRecord
from app.schemas.common import NewForm, Page, enum_options
from app.schemas.set_record import SetRecordDefaults, SetRecordPut, SetRecordRead

# The sets a user actually did: their history of each exercise, logged with PUT and a
# client-generated id so a retry after a dropped connection can't log a set twice
router = APIRouter(tags=["set-records"])

NEWEST_FIRST = (SetRecord.performed_at.desc(), SetRecord.id.desc())


def get_own_record(db: Session, id: uuid.UUID, user_id: uuid.UUID) -> SetRecord:
    record = db.get(SetRecord, id)
    if record is None or record.user_id != user_id:
        raise not_found()
    return record


@router.get("/exercises/{exercise_id}/set-records")
def index(
    exercise_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    since: Annotated[AwareDatetime | None, Query(description="From this time, inclusive")] = None,
    until: Annotated[AwareDatetime | None, Query(description="Before this time")] = None,
    before: Annotated[
        AwareDatetime | None,
        Query(description="The `performed_at` of the last record already shown; pages back"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 50,
) -> Page[SetRecordRead]:
    """The user's records of the exercise, newest first. Page back by passing the last
    record's `performed_at` as `before`. A page runs past `limit` when needed so records with
    the same `performed_at` are never split across pages. `total` counts every match"""
    exercise = get_visible_or_404(db, Exercise, exercise_id, user.id)
    filters = [SetRecord.user_id == user.id, SetRecord.exercise_id == exercise.id]
    if since is not None:
        filters.append(SetRecord.performed_at >= since)
    if until is not None:
        filters.append(SetRecord.performed_at < until)
    if before is not None:
        filters.append(SetRecord.performed_at < before)
    records = list(
        db.scalars(select(SetRecord).where(*filters).order_by(*NEWEST_FIRST).limit(limit))
    )
    if len(records) == limit:
        # Finish the last timestamp, so paging with `before` doesn't skip records sharing it
        records += db.scalars(
            select(SetRecord)
            .where(
                *filters,
                SetRecord.performed_at == records[-1].performed_at,
                SetRecord.id < records[-1].id,
            )
            .order_by(*NEWEST_FIRST)
        )
    total = db.scalar(select(func.count()).select_from(SetRecord).where(*filters)) or 0
    return Page(items=[SetRecordRead.model_validate(record) for record in records], total=total)


@router.get("/exercises/{exercise_id}/set-records/new")
def new(exercise_id: uuid.UUID, user: CurrentUser, db: DbSession) -> NewForm[SetRecordDefaults]:
    """Suggested values for logging the exercise: the user's latest record of it, or just
    their preferred unit"""
    exercise = get_visible_or_404(db, Exercise, exercise_id, user.id)
    latest = db.scalar(
        select(SetRecord)
        .where(SetRecord.user_id == user.id, SetRecord.exercise_id == exercise.id)
        .order_by(*NEWEST_FIRST)
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
    if the id is another user's record; 422 unless the exercise is a library one or the
    user's own"""
    record = db.get(SetRecord, id)
    if record is not None and record.user_id != user.id:
        raise ApiError(
            status.HTTP_409_CONFLICT, "id_conflict", "That id is already used; generate a new one"
        )
    exercise = get_usable_exercise(db, body.exercise_id, user.id)
    if record is None:
        record = SetRecord(id=id, user_id=user.id, performed_at=body.performed_at or now())
        db.add(record)
        response.status_code = status.HTTP_201_CREATED
    elif body.performed_at is not None:
        record.performed_at = body.performed_at
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
    db.delete(get_own_record(db, id, user.id))
