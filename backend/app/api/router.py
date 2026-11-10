from fastapi import APIRouter

from app.api.routes import health, password, profile, registration, session, sessions

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(registration.router)
api_router.include_router(session.router)
api_router.include_router(sessions.router)
api_router.include_router(profile.router)
api_router.include_router(password.router)
