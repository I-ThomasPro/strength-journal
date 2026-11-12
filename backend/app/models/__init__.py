"""Every model module, imported so all mappers are registered whenever any model is used.

Relationships refer to other models by name (e.g. Routine.workouts -> "Workout"), which only
resolves once every module is loaded. Add new model modules here.
"""

from app.models import (  # noqa: F401
    exercise,
    invite,
    routine,
    routine_workout,
    set,
    set_record,
    user,
    user_session,
    workout,
)
