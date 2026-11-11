import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, Field

from app.models.common import WeightUnit
from app.schemas.common import ReadModel, Weight

# Reps actually completed; 0 records a failed attempt
Reps = Annotated[int, Field(ge=0, le=1000)]


class SetRecordPut(BaseModel):
    """A whole record, created or replaced under the id in the path"""

    # A library exercise or one of the user's own
    exercise_id: uuid.UUID
    reps: Reps
    weight: Weight
    # Defaults to the user's preferred unit
    weight_unit: WeightUnit | None = None
    # With a timezone. Defaults to now for a new record, and to the stored time when
    # replacing, so retrying the same request doesn't move the record
    performed_at: AwareDatetime | None = None


class SetRecordDefaults(BaseModel):
    """What `new` suggests: the user's latest record of the exercise, if there is one"""

    reps: int | None
    weight: Decimal | None
    weight_unit: WeightUnit


class SetRecordRead(ReadModel):
    """A set the user actually did"""

    id: uuid.UUID
    exercise_id: uuid.UUID
    reps: int
    weight: Decimal
    weight_unit: WeightUnit
    performed_at: datetime
    created_at: datetime
    updated_at: datetime
