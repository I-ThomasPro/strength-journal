import uuid
from datetime import datetime
from decimal import Decimal

from app.models.common import WeightUnit
from app.schemas.common import ReadModel


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
