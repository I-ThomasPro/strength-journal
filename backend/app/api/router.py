from fastapi import APIRouter

from app.api.routes import (
    exercises,
    health,
    password,
    profile,
    progressions,
    registration,
    routines,
    session,
    sessions,
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
api_router.include_router(workouts.router)
api_router.include_router(workout_exercises.router)
api_router.include_router(progressions.router)
