import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.common import WeightUnit
from app.schemas.common import Position, ReadModel, Weight

# Reps actually completed; 0 records a failed attempt
Reps = Annotated[int, Field(ge=0, le=1000)]


class SetRecordPut(BaseModel):
    """A whole record, created or replaced under the id in the path"""

    # One of the user's own sessions
    session_id: uuid.UUID
    # A library exercise or one of the user's own
    exercise_id: uuid.UUID
    # The prescribed set it was done against, if any: a set in the session's workout. Its
    # targets are copied onto the record when it's first linked
    set_id: uuid.UUID | None = None
    # Without one, a new record goes at the end of the session and an existing one stays put
    position: Position | None = None
    reps: Reps
    weight: Weight
    # Defaults to the user's preferred unit
    weight_unit: WeightUnit | None = None


class SetRecordOrder(BaseModel):
    """Every one of the session's records, in their new order"""

    set_record_ids: list[uuid.UUID]


class SetRecordDefaults(BaseModel):
    """What `new` suggests: a prescribed set's targets, or the user's latest record of the
    exercise, if there is one"""

    reps: int | None
    weight: Decimal | None
    weight_unit: WeightUnit


class SetRecordRead(ReadModel):
    """A set the user actually did, at a position in one of their sessions"""

    id: uuid.UUID
    session_id: uuid.UUID
    exercise_id: uuid.UUID
    set_id: uuid.UUID | None
    position: int
    reps: int
    weight: Decimal
    weight_unit: WeightUnit
    # What the linked set prescribed when it was linked; null for an unlinked record
    target_reps: int | None
    target_weight: Decimal | None
    target_unit: WeightUnit | None
    # The session's time
    performed_at: datetime
    created_at: datetime
    updated_at: datetime
