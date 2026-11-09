"""The route rules every `/api` endpoint must follow (enforced by tests/test_restful_routes.py)

Resources use the Rails actions by default, with shallow nesting:

    index    GET     /api/[{parents}/{parent_id}/]{resources}
    new      GET     /api/[{parents}/{parent_id}/]{resources}/new
    create   POST    /api/[{parents}/{parent_id}/]{resources}
    show     GET     /api/{resources}/{id}            (or /api/{resource} if singular)
    edit     GET     /api/{resources}/{id}/edit       (or /api/{resource}/edit)
    update   PATCH   /api/{resources}/{id}            (or /api/{resource})
    destroy  DELETE  /api/{resources}/{id}            (or /api/{resource})

Endpoint functions are named after their action, so operation IDs read `{tag}-{action}`.
A resource only needs the actions it uses; `new` and `edit` exist only where the server
supplies defaults the client can't know.

Anything else is a custom route: allowed when a standard action would hide what it does
(copying, bulk reordering, idempotent create-or-replace), but it must be registered in
CUSTOM_ROUTES with the reason, and its function must not reuse a standard action's name.
"""

import re
from collections.abc import Iterable, Mapping

from fastapi import FastAPI
from fastapi.routing import APIRoute

API_PREFIX = "/api"
NAME = re.compile(r"^[a-z]+(-[a-z]+)*$")
PARENT_ID = re.compile(r"^\{[a-z]+(_[a-z]+)*_id\}$")
MEMBER_ID = "{id}"

# action -> (HTTP method, allowed path shapes)
# Shapes use: R = resource name, P = parent resource name, PID = {parent_id}, ID = {id}
ACTIONS: dict[str, tuple[str, tuple[tuple[str, ...], ...]]] = {
    "index": ("GET", (("R",), ("P", "PID", "R"))),
    "new": ("GET", (("R", "new"), ("P", "PID", "R", "new"))),
    "create": ("POST", (("R",), ("P", "PID", "R"))),
    "show": ("GET", (("R", "ID"), ("R",))),
    "edit": ("GET", (("R", "ID", "edit"), ("R", "edit"))),
    "update": ("PATCH", (("R", "ID"), ("R",))),
    "destroy": ("DELETE", (("R", "ID"), ("R",))),
}

# Routes outside the standard actions: (method, path) -> why a standard action doesn't fit.
# Add an entry in the same change that adds the route.
CUSTOM_ROUTES: dict[tuple[str, str], str] = {}


def _matches(segments: list[str], shape: tuple[str, ...]) -> bool:
    if len(segments) != len(shape):
        return False
    for segment, part in zip(segments, shape, strict=True):
        if part in ("R", "P"):
            ok = bool(NAME.match(segment)) and segment not in ("new", "edit")
        elif part == "PID":
            ok = bool(PARENT_ID.match(segment))
        elif part == "ID":
            ok = segment == MEMBER_ID
        else:
            ok = segment == part
        if not ok:
            return False
    return True


def _standard_violation(method: str, path: str, name: str) -> str | None:
    label = f"{method} {path} ({name})"
    if name not in ACTIONS:
        return (
            f"{label}: name the function after an action ({', '.join(ACTIONS)}), "
            "or register it in CUSTOM_ROUTES with a reason"
        )
    expected_method, shapes = ACTIONS[name]
    if method != expected_method:
        return f"{label}: `{name}` must use {expected_method}, or register a custom route"
    if not path.startswith(API_PREFIX + "/"):
        return f"{label}: must be under {API_PREFIX}/"
    segments = path.removeprefix(API_PREFIX + "/").split("/")
    if not any(_matches(segments, shape) for shape in shapes):
        return (
            f"{label}: path doesn't fit the `{name}` shape; "
            "if it's a custom route, register it in CUSTOM_ROUTES with a reason"
        )
    return None


def route_violation(
    method: str,
    path: str,
    name: str,
    custom_routes: Mapping[tuple[str, str], str] = CUSTOM_ROUTES,
) -> str | None:
    """Why a route breaks the rules, or None if it follows them"""
    reason = custom_routes.get((method, path))
    if reason is None:
        return _standard_violation(method, path, name)
    label = f"{method} {path} ({name})"
    if not reason.strip():
        return f"{label}: give its CUSTOM_ROUTES entry a reason"
    if name in ACTIONS:
        return f"{label}: name a custom route's function after what it does, not `{name}`"
    return None


def _api_routes(routes: Iterable[object]) -> Iterable[tuple[str, str, str]]:
    """(method, path, name) for every API route; docs and OpenAPI routes aren't APIRoutes"""
    for route in routes:
        if isinstance(route, APIRoute) and route.path.startswith(API_PREFIX):
            for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                yield method, route.path, route.name


def route_violations(
    routes: Iterable[object], custom_routes: Mapping[tuple[str, str], str] = CUSTOM_ROUTES
) -> list[str]:
    problems = []
    for method, path, name in _api_routes(routes):
        problem = route_violation(method, path, name, custom_routes)
        if problem:
            problems.append(problem)
    return problems


def stale_custom_routes(
    routes: Iterable[object], custom_routes: Mapping[tuple[str, str], str] = CUSTOM_ROUTES
) -> list[tuple[str, str]]:
    """Registered custom routes that no longer exist, so the register can't go stale"""
    existing = {(method, path) for method, path, _name in _api_routes(routes)}
    return sorted(set(custom_routes) - existing)


def app_route_violations(app: FastAPI) -> list[str]:
    return route_violations(app.routes) + [
        f"{method} {path}: registered in CUSTOM_ROUTES but no such route exists"
        for method, path in stale_custom_routes(app.routes)
    ]
