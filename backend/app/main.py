from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.api.errors import register_error_handlers
from app.api.router import api_router
from app.auth.guards import register_request_guards
from app.config import get_settings
from app.schemas.common import ErrorBody


def generate_operation_id(route: APIRoute) -> str:
    """Name operations `{tag}-{action}` (functions are named after their action, e.g.
    `exercises-create`), so generated API clients read cleanly"""
    tag = route.tags[0] if route.tags else "default"
    return f"{tag}-{route.name}"


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        # Keep everything under /api so the frontend can own all other paths
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        generate_unique_id_function=generate_operation_id,
        # Document our validation error shape (see app/api/errors.py) on every route, instead
        # of FastAPI's default HTTPValidationError, so generated clients get the right type
        responses={422: {"model": ErrorBody, "description": "Validation error"}},
    )
    register_error_handlers(app)
    register_request_guards(app)
    app.include_router(api_router)
    return app


app = create_app()
