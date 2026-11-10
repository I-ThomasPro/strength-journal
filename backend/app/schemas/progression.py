import uuid
from datetime import datetime
from decimal import Decimal

from app.models.common import WeightUnit
from app.models.progression import ProgressionCondition
from app.schemas.common import ReadModel
from app.schemas.exercise import ExerciseSummary


class ProgressionRead(ReadModel):
    """How much weight an exercise in a routine gains each time `condition` is met"""

    id: uuid.UUID
    routine_id: uuid.UUID
    exercise: ExerciseSummary
    increment: Decimal
    increment_unit: WeightUnit
    condition: ProgressionCondition
    created_at: datetime
    updated_at: datetime
