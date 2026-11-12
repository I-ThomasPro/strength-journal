import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.common import WeightUnit
from app.schemas.common import ReadModel


class RoutineCycleRead(ReadModel):
    """One pass through a routine's slots; `completed_at` is null while it's open"""

    id: uuid.UUID
    number: int
    started_at: datetime
    completed_at: datetime | None


class RoutineCycleSummary(ReadModel):
    """The cycle a workout session belongs to"""

    id: uuid.UUID
    routine_id: uuid.UUID
    number: int


class SetTargetChange(BaseModel):
    """A prescribed set whose target weight was carried forward from what was lifted"""

    set_id: uuid.UUID
    workout_exercise_id: uuid.UUID
    from_weight: Decimal
    from_unit: WeightUnit
    to_weight: Decimal
    to_unit: WeightUnit


class NewCycleRead(RoutineCycleRead):
    """The cycle just opened, and the sets whose targets changed to start it"""

    changed_sets: list[SetTargetChange]
