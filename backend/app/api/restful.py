"""The RESTful route rules every `/api` endpoint must follow (enforced by a test)

Only the seven Rails actions, with shallow nesting:

    index    GET     /api/[{parents}/{parent_id}/]{resources}
    new      GET     /api/[{parents}/{parent_id}/]{resources}/new
    create   POST    /api/[{parents}/{parent_id}/]{resources}
    show     GET     /api/{resources}/{id}            (or /api/{resource} if singular)
    edit     GET     /api/{resources}/{id}/edit       (or /api/{resource}/edit)
    update   PATCH   /api/{resources}/{id}            (or /api/{resource})
    destroy  DELETE  /api/{resources}/{id}            (or /api/{resource})

Endpoint functions are named after their action, so operation IDs read `{tag}-{action}`.
"""

import re
from collections.abc import Iterable

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


def route_violation(method: str, path: str, name: str) -> str | None:
    """Why a route breaks the rules, or None if it follows them"""
    label = f"{method} {path} ({name})"
    if name not in ACTIONS:
        return f"{label}: function must be named after an action: {', '.join(ACTIONS)}"
    expected_method, shapes = ACTIONS[name]
    if method != expected_method:
        return f"{label}: `{name}` must use {expected_method}"
    if not path.startswith(API_PREFIX + "/"):
        return f"{label}: must be under {API_PREFIX}/"
    segments = path.removeprefix(API_PREFIX + "/").split("/")
    if not any(_matches(segments, shape) for shape in shapes):
        return f"{label}: path doesn't fit the `{name}` shape"
    return None


def route_violations(routes: Iterable[object]) -> list[str]:
    """Check every API route (docs and OpenAPI routes aren't APIRoutes, so they're skipped)"""
    problems = []
    for route in routes:
        if not isinstance(route, APIRoute) or not route.path.startswith(API_PREFIX):
            continue
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            problem = route_violation(method, route.path, route.name)
            if problem:
                problems.append(problem)
    return problems


def app_route_violations(app: FastAPI) -> list[str]:
    return route_violations(app.routes)
