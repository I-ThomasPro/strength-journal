"""One error format for the whole API: `{"detail": "...", "code": "..."}`"""

from http import HTTPStatus

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from psycopg import errors as pg_errors
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import ErrorBody


class ApiError(Exception):
    """Raise from an endpoint to return an error response with a stable `code`"""

    def __init__(self, status_code: int, code: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail


def not_found(detail: str = "Not found") -> ApiError:
    """Missing, or belongs to another user (the two aren't told apart)"""
    return ApiError(status.HTTP_404_NOT_FOUND, "not_found", detail)


def read_only(detail: str = "Library items can't be changed") -> ApiError:
    return ApiError(status.HTTP_403_FORBIDDEN, "read_only", detail)


def invalid(detail: str) -> ApiError:
    """A well-formed request that can't be applied, e.g. a reference to a missing item"""
    return ApiError(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid", detail)


# Database constraints whose violation means something specific to the client.
# Deferred foreign keys report at commit, so they're matched by name, not by statement.
CONSTRAINT_ERRORS: dict[str, tuple[str, str]] = {
    "uq_users_email": ("duplicate_email", "An account with this email already exists"),
    "uq_exercises_owner_id_lower_name": (
        "duplicate_name",
        "You already have an exercise with this name",
    ),
    "fk_workout_exercises_exercise_id_exercises": (
        "exercise_in_use",
        "This exercise is used in a workout",
    ),
    "fk_set_records_exercise_id_exercises": (
        "exercise_in_use",
        "This exercise has recorded sets",
    ),
}

HTTP_ERROR_CODES = {
    status.HTTP_401_UNAUTHORIZED: "not_authenticated",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "method_not_allowed",
}


def error_response(
    status_code: int, code: str, detail: str, errors: list | None = None
) -> JSONResponse:
    body = ErrorBody(detail=detail, code=code, errors=errors)
    return JSONResponse(status_code=status_code, content=body.model_dump(exclude_none=True))


def integrity_error_response(exc: IntegrityError) -> JSONResponse:
    """Map a constraint violation (at flush or at commit) to a 409 or 422"""
    diag = getattr(exc.orig, "diag", None)
    constraint = getattr(diag, "constraint_name", None)
    if constraint in CONSTRAINT_ERRORS:
        code, detail = CONSTRAINT_ERRORS[constraint]
        return error_response(status.HTTP_409_CONFLICT, code, detail)
    if isinstance(exc.orig, pg_errors.CheckViolation | pg_errors.NotNullViolation):
        # Pydantic validation should catch these first; this is the database's backstop
        return error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid", "A value is not allowed"
        )
    return error_response(
        status.HTTP_409_CONFLICT, "conflict", "The change conflicts with existing data"
    )


def sanitized_validation_errors(exc: RequestValidationError) -> list:
    """Validation errors without the submitted values: each error's `input` can hold a
    password, an invite code or the whole request body, which must never be echoed back"""
    return jsonable_encoder(
        [{key: value for key, value in error.items() if key != "input"} for error in exc.errors()]
    )


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_request: Request, exc: ApiError) -> JSONResponse:
        return error_response(exc.status_code, exc.code, exc.detail)

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(_request: Request, exc: IntegrityError) -> JSONResponse:
        return integrity_error_response(exc)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid",
            "The request is invalid",
            errors=sanitized_validation_errors(exc),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = HTTP_ERROR_CODES.get(exc.status_code, "http_error")
        detail = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
        response = error_response(exc.status_code, code, detail)
        if exc.headers:
            response.headers.update(exc.headers)
        return response
