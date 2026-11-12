import uuid

from fastapi import APIRouter
from sqlalchemy import select

from app.api.pagination import PageQuery, paginate
from app.api.routine_parts import get_own_session, reorder
from app.auth.sessions import CurrentUser
from app.db import DbSession
from app.models.set_record import SetRecord
from app.schemas.common import Page
from app.schemas.set_record import SetRecordOrder, SetRecordRead

# A workout session's set records, in order. Logging, changing and deleting a record is in
# set_records.py. A separate tag from set-records, so `session-set-records-index` doesn't
# clash with the exercise history's `set-records-index`
router = APIRouter(tags=["session-set-records"])


@router.get("/workout-sessions/{workout_session_id}/set-records")
def index(
    workout_session_id: uuid.UUID, user: CurrentUser, db: DbSession, page: PageQuery
) -> Page[SetRecordRead]:
    """The session's records in position order"""
    session = get_own_session(db, workout_session_id, user.id)
    statement = (
        select(SetRecord).where(SetRecord.session_id == session.id).order_by(SetRecord.position)
    )
    records, total = paginate(db, statement, page)
    return Page(items=[SetRecordRead.model_validate(record) for record in records], total=total)


@router.put("/workout-sessions/{workout_session_id}/set-records/order")
def order(
    workout_session_id: uuid.UUID, body: SetRecordOrder, user: CurrentUser, db: DbSession
) -> list[SetRecordRead]:
    """Set the order of all the session's records at once; returns them in the new order"""
    session = get_own_session(db, workout_session_id, user.id)
    session.set_records = reorder(session.set_records, body.set_record_ids, "session's records")
    db.flush()
    return [SetRecordRead.model_validate(record) for record in session.set_records]
