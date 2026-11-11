import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.common import WeightUnit
from app.models.progression import ProgressionCondition
from app.schemas.common import ReadModel, UpdateModel, Weight, omitted
from app.schemas.exercise import ExerciseSummary

# Weight added each time the condition is met: above 0
Increment = Annotated[Weight, Field(gt=0)]


class ProgressionCreate(BaseModel):
    # Must be used in one of the routine's workouts
    exercise_id: uuid.UUID
    increment: Increment
    # Defaults to the user's preferred unit
    increment_unit: WeightUnit | None = None
    condition: ProgressionCondition = ProgressionCondition.ALL_SETS_COMPLETED


class ProgressionUpdate(UpdateModel):
    increment: Increment = omitted()
    increment_unit: WeightUnit = omitted()
    condition: ProgressionCondition = omitted()


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
