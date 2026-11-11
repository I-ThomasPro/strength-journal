"""The route rules every `/api` endpoint must follow (enforced by tests/test_restful_routes.py)

Resources use the Rails actions by default, with shallow nesting:

    index    GET     /api/[{parents}/{parent_id}/]{resources}
    new      GET     /api/[{parents}/{parent_id}/]{resources}/new
    create   POST    /api/[{parents}/{parent_id}/]{resources}
    show     GET     /api/{resources}/{id}
    edit     GET     /api/{resources}/{id}/edit
    update   PATCH   /api/{resources}/{id}
    destroy  DELETE  /api/{resources}/{id}

A parent's id parameter is named after it: /api/routines/{routine_id}/workouts.

Singular resources (one per user or app, listed in SINGULAR_RESOURCES) have no index and
no {id}: new (/api/{resource}/new), create, show, update, destroy (/api/{resource}) and
edit (/api/{resource}/edit). They can't be nested or be a parent.

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
from fastapi.routing import APIRoute, iter_route_contexts
from starlette.routing import BaseRoute

API_PREFIX = "/api"
NAME = re.compile(r"^[a-z]+(-[a-z]+)*$")
MEMBER_ID = "{id}"

# Resources with one instance per user (or for the app), so no index and no {id}.
# Add a resource here when it's created as singular.
SINGULAR_RESOURCES = frozenset({"health", "registration", "session", "profile", "password"})

# Shapes use: R = resource name, P = parent resource name, PID = {parent_id}, ID = {id}
type Shapes = tuple[tuple[str, ...], ...]

# action -> (HTTP method, path shapes for plural resources, path shapes for singular ones)
ACTIONS: dict[str, tuple[str, Shapes, Shapes]] = {
    "index": ("GET", (("R",), ("P", "PID", "R")), ()),
    "new": ("GET", (("R", "new"), ("P", "PID", "R", "new")), (("R", "new"),)),
    "create": ("POST", (("R",), ("P", "PID", "R")), (("R",),)),
    "show": ("GET", (("R", "ID"),), (("R",),)),
    "edit": ("GET", (("R", "ID", "edit"),), (("R", "edit"),)),
    "update": ("PATCH", (("R", "ID"),), (("R",),)),
    "destroy": ("DELETE", (("R", "ID"),), (("R",),)),
}

# Routes outside the standard actions: (method, path) -> why a standard action doesn't fit.
# Add an entry in the same change that adds the route.
REORDER = "Replaces the whole order in one request, which `PATCH position` can't"
CUSTOM_ROUTES: dict[tuple[str, str], str] = {
    ("PUT", "/api/routines/{routine_id}/workouts/order"): REORDER,
    ("PUT", "/api/workouts/{workout_id}/workout-exercises/order"): REORDER,
    ("PUT", "/api/workout-exercises/{workout_exercise_id}/sets/order"): REORDER,
}


def parent_id_param(parent: str) -> str:
    """The id parameter in a nested path, e.g. `workout-exercises` → `{workout_exercise_id}`"""
    return "{" + parent.replace("-", "_").removesuffix("s") + "_id}"


def _is_name(segment: str) -> bool:
    return bool(NAME.match(segment)) and segment not in ("new", "edit")


def _matches(segments: list[str], shape: tuple[str, ...], singular: bool) -> bool:
    """Does the path fit the shape, with R singular or plural as required?"""
    if len(segments) != len(shape):
        return False
    for index, (segment, part) in enumerate(zip(segments, shape, strict=True)):
        if part == "R":
            ok = _is_name(segment) and (segment in SINGULAR_RESOURCES) == singular
        elif part == "P":
            ok = _is_name(segment) and segment not in SINGULAR_RESOURCES
        elif part == "PID":
            ok = segment == parent_id_param(segments[index - 1])
        elif part == "ID":
            ok = segment == MEMBER_ID
        else:
            ok = segment == part
        if not ok:
            return False
    return True


MEMBER_ACTIONS = ("show", "edit", "update", "destroy")


def _shape_hint(segments: list[str], name: str) -> str:
    """A specific reason a path doesn't fit, where one is easy to spot"""
    resource = segments[0]
    nested = len(segments) >= 3 and segments[1].startswith("{") and segments[1] != MEMBER_ID
    if nested and _is_name(resource) and segments[1] != parent_id_param(resource):
        return f"; the parent parameter should be {parent_id_param(resource)}"
    if resource in SINGULAR_RESOURCES:
        return f"; `{resource}` is singular (no index, no {{id}}, not a parent)"
    if name in MEMBER_ACTIONS and MEMBER_ID not in segments:
        return (
            f"; `{name}` on a plural resource needs /{{id}} "
            "(add the resource to SINGULAR_RESOURCES if it's singular)"
        )
    return ""


def _standard_violation(method: str, path: str, name: str) -> str | None:
    label = f"{method} {path} ({name})"
    if name not in ACTIONS:
        return (
            f"{label}: name the function after an action ({', '.join(ACTIONS)}), "
            "or register it in CUSTOM_ROUTES with a reason"
        )
    expected_method, plural_shapes, singular_shapes = ACTIONS[name]
    if method != expected_method:
        return f"{label}: `{name}` must use {expected_method}, or register a custom route"
    if not path.startswith(API_PREFIX + "/"):
        return f"{label}: must be under {API_PREFIX}/"
    segments = path.removeprefix(API_PREFIX + "/").split("/")
    fits = any(_matches(segments, shape, singular=False) for shape in plural_shapes) or any(
        _matches(segments, shape, singular=True) for shape in singular_shapes
    )
    if not fits:
        return (
            f"{label}: path doesn't fit the `{name}` shape{_shape_hint(segments, name)}; "
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


def api_routes(routes: Iterable[BaseRoute]) -> Iterable[tuple[str, str, str]]:
    """(method, path, name) for every API route; docs and OpenAPI routes aren't APIRoutes.

    FastAPI keeps an included router as one wrapper in `app.routes`, so this goes through
    `iter_route_contexts()`, which yields each route inside with its full path.
    """
    for context in iter_route_contexts(list(routes)):
        if isinstance(context.original_route, APIRoute) and context.path.startswith(API_PREFIX):
            for method in sorted(set(context.methods or ()) - {"HEAD", "OPTIONS"}):
                yield method, context.path, context.name


def route_violations(
    routes: Iterable[BaseRoute], custom_routes: Mapping[tuple[str, str], str] = CUSTOM_ROUTES
) -> list[str]:
    problems = []
    for method, path, name in api_routes(routes):
        problem = route_violation(method, path, name, custom_routes)
        if problem:
            problems.append(problem)
    return problems


def stale_custom_routes(
    routes: Iterable[BaseRoute], custom_routes: Mapping[tuple[str, str], str] = CUSTOM_ROUTES
) -> list[tuple[str, str]]:
    """Registered custom routes that no longer exist, so the register can't go stale"""
    existing = {(method, path) for method, path, _name in api_routes(routes)}
    return sorted(set(custom_routes) - existing)


def app_route_violations(app: FastAPI) -> list[str]:
    return route_violations(app.routes) + [
        f"{method} {path}: registered in CUSTOM_ROUTES but no such route exists"
        for method, path in stale_custom_routes(app.routes)
    ]
