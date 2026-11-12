from fastapi import APIRouter

from app.api.routes import (
    exercises,
    health,
    password,
    profile,
    registration,
    routine_workouts,
    routines,
    session,
    sessions,
    set_records,
    sets,
    workout_exercises,
    workouts,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(registration.router)
api_router.include_router(session.router)
api_router.include_router(sessions.router)
api_router.include_router(profile.router)
api_router.include_router(password.router)
api_router.include_router(exercises.router)
api_router.include_router(routines.router)
api_router.include_router(routine_workouts.router)
api_router.include_router(workouts.router)
api_router.include_router(workout_exercises.router)
api_router.include_router(sets.router)
api_router.include_router(set_records.router)
