import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, StringConstraints

from app.schemas.common import ReadModel, UpdateModel, omitted
from app.schemas.progression import ProgressionRead
from app.schemas.workout import WorkoutDetail

RoutineName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
# Optional free text; blank is stored as no description
Description = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None,
    AfterValidator(lambda description: description or None),
]


class RoutineCreate(BaseModel):
    name: RoutineName
    description: Description = None


class RoutineUpdate(UpdateModel):
    name: RoutineName = omitted()
    # null (or blank) clears it
    description: Description = None


class RoutineFields(ReadModel):
    id: uuid.UUID
    name: str
    description: str | None
    is_library: bool
    # The library routine this one was copied from, if any
    source_routine_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class RoutineSummary(RoutineFields):
    """A routine in a list"""

    workout_count: int


class RoutineDetail(RoutineFields):
    """Everything in a routine, each list in position order"""

    workouts: list[WorkoutDetail]
    progressions: list[ProgressionRead]
