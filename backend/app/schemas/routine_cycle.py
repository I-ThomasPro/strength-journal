import uuid
from datetime import datetime

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
