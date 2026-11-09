"""Checks on every unsafe API request, logged in or not (login and sign-up included):

- An Origin header, when sent, must be the configured frontend origin. Browsers send it on
  cross-site requests, so this stops other sites posting to the API
- Bodies must be JSON, which HTML forms on other sites can't send
"""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response, status

from app.api.errors import error_response
from app.auth.sessions import SAFE_METHODS
from app.config import get_settings


def _has_body(request: Request) -> bool:
    length = request.headers.get("content-length")
    return (length is not None and length != "0") or "transfer-encoding" in request.headers


def _is_json(request: Request) -> bool:
    content_type = request.headers.get("content-type", "")
    return content_type.split(";")[0].strip().lower() == "application/json"


def register_request_guards(app: FastAPI) -> None:
    @app.middleware("http")
    async def guard_unsafe_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method not in SAFE_METHODS and request.url.path.startswith("/api/"):
            origin = request.headers.get("origin")
            if origin is not None and origin != get_settings().allowed_origin:
                return error_response(
                    status.HTTP_403_FORBIDDEN,
                    "bad_origin",
                    "Requests from this origin aren't allowed",
                )
            if _has_body(request) and not _is_json(request):
                return error_response(
                    status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    "unsupported_media_type",
                    "Send request bodies as application/json",
                )
        return await call_next(request)
