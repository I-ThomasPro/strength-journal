from fastapi import APIRouter

from app.api.routes import health, registration, session

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(registration.router)
api_router.include_router(session.router)
