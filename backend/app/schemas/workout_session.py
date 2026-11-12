import uuid
from datetime import datetime

from pydantic import AwareDatetime, BaseModel

from app.schemas.common import ReadModel, UpdateModel, omitted
from app.schemas.routine_cycle import RoutineCycleSummary
from app.schemas.workout import WorkoutSummary


class WorkoutSessionPut(BaseModel):
    """A session created, or changed, under a client-generated id. Creating fills in what's
    left out (freestyle, now, not completed); on an existing session only the fields sent
    change, so retrying the same request is safe"""

    # A slot in one of the user's own routines; null (or left out on create) for freestyle
    routine_workout_id: uuid.UUID | None = None
    # With a timezone; back-dating is allowed
    performed_at: AwareDatetime = omitted()
    completed: bool = omitted()


class WorkoutSessionUpdate(UpdateModel):
    performed_at: AwareDatetime = omitted()
    completed: bool = omitted()


class RoutineWorkoutSummary(ReadModel):
    """The slot a session was done from"""

    id: uuid.UUID
    position: int


class WorkoutSessionRead(ReadModel):
    """One time the user performed a workout. The slot, workout and cycle are null for a
    freestyle session, and each becomes null if it's deleted later"""

    id: uuid.UUID
    routine_workout: RoutineWorkoutSummary | None
    workout: WorkoutSummary | None
    cycle: RoutineCycleSummary | None
    performed_at: datetime
    completed: bool
    created_at: datetime
    updated_at: datetime
