import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, StringConstraints

from app.schemas.common import ReadModel, UpdateModel, omitted
from app.schemas.routine_cycle import RoutineCycleRead
from app.schemas.routine_workout import RoutineWorkoutRead
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


class RoutineCopy(BaseModel):
    """Both default to the original's. Sending `description: null` leaves the copy without one"""

    name: RoutineName | None = None
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
    """Everything in a routine: its workouts (in the order they were added, each with its
    exercises and sets in position order) and its cycle of slots in position order"""

    workouts: list[WorkoutDetail]
    slots: list[RoutineWorkoutRead]
    # The open cycle; null only for a routine that has never had one
    current_cycle: RoutineCycleRead | None = None
    # The slot to do next in the current cycle: the one after the user's latest completed
    # session, or the first if none is. Null once the last slot is done (time for the next
    # cycle), or if the routine has no slots
    next_slot: RoutineWorkoutRead | None = None
