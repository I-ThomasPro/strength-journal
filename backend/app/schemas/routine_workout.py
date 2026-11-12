import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import Position, ReadModel, UpdateModel, omitted
from app.schemas.workout import WorkoutSummary


class RoutineWorkoutCreate(BaseModel):
    # One of the routine's workouts; it can fill several slots
    workout_id: uuid.UUID
    # Without one, the slot is added at the end of the cycle
    position: Position | None = None


class RoutineWorkoutUpdate(UpdateModel):
    # Puts a different one of the routine's workouts in this slot
    workout_id: uuid.UUID = omitted()
    # Moves the slot; the others shift to make room
    position: Position = omitted()


class RoutineWorkoutOrder(BaseModel):
    """Every one of the routine's slots, in their new order"""

    routine_workout_ids: list[uuid.UUID]


class RoutineWorkoutRead(ReadModel):
    """A slot in a routine's cycle: which workout comes at this position"""

    id: uuid.UUID
    routine_id: uuid.UUID
    position: int
    workout: WorkoutSummary
    created_at: datetime
    updated_at: datetime
