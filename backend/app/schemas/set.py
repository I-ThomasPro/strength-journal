import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.common import WeightUnit
from app.schemas.common import Position, ReadModel, UpdateModel, Weight, omitted

# Reps to complete in one set; the upper bound only keeps out nonsense
Reps = Annotated[int, Field(gt=0, le=1000)]


class SetCreate(BaseModel):
    target_reps: Reps
    target_weight: Weight
    # Defaults to the user's preferred unit
    weight_unit: WeightUnit | None = None
    # Without one, the set is added at the end
    position: Position | None = None


class SetUpdate(UpdateModel):
    target_reps: Reps = omitted()
    target_weight: Weight = omitted()
    weight_unit: WeightUnit = omitted()
    # Moves the set; the others shift to make room
    position: Position = omitted()


class SetOrder(BaseModel):
    """Every one of the workout exercise's sets, in their new order"""

    set_ids: list[uuid.UUID]


class SetDefaults(BaseModel):
    """What `new` suggests for the next set: the last set's targets, if there is one"""

    target_reps: int | None
    target_weight: Decimal | None
    weight_unit: WeightUnit


class SetRead(ReadModel):
    """One set to complete: the reps and weight a routine prescribes"""

    id: uuid.UUID
    workout_exercise_id: uuid.UUID
    position: int
    target_reps: int
    target_weight: Decimal
    weight_unit: WeightUnit
    created_at: datetime
    updated_at: datetime
