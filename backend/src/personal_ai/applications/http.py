"""Attach selected trusted HTTP contributions with unambiguous ownership."""

import re

from fastapi import APIRouter


def _paths_overlap(left, right):
    """Conservatively reject overlapping templates, including renamed parameters."""
    left_parts, right_parts = left.path.split("/"), right.path.split("/")
    for one, two in zip(left_parts, right_parts, strict=False):
        if ":path}" in one or ":path}" in two:
            return True
        one_parameter, two_parameter = "{" in one, "{" in two
        if not one_parameter and not two_parameter:
            if one != two:
                return False
        elif one_parameter != two_parameter:
            parameter, literal, route = (one, two, left) if one_parameter else (two, one, right)
            match = re.fullmatch(r"\{([^}:]+)(?::[^}]+)?\}", parameter)
            if match and re.fullmatch(route.param_convertors[match[1]].regex, literal) is None:
                return False
    return len(left_parts) == len(right_parts)


def _http_routes(routes):
    # FastAPI supports both eager APIRoute lists and lazy included routers.
    for route in routes:
        effective = getattr(route, "effective_route_contexts", None)
        if callable(effective):
            yield from effective()
        else:
            if not hasattr(route, "path") or not getattr(route, "methods", None):
                raise TypeError("application_route_introspection_unavailable")
            yield route


def attach_contribution_routes(application, contributions):
    """Validate the entire route/error set before changing the app."""
    routers, handlers = [], {}
    for contribution in contributions:
        for router in contribution.routers:
            if not isinstance(router, APIRouter):
                raise TypeError("application_router_invalid")
            if not any(router is existing for existing in routers):
                routers.append(router)
        for error_type, handler in (contribution.exception_handlers or {}).items():
            if (
                not isinstance(error_type, type)
                or not issubclass(error_type, Exception)
                or not callable(handler)
            ):
                raise TypeError("application_exception_handler_invalid")
            existing = handlers.get(error_type, application.exception_handlers.get(error_type))
            if existing is not None and existing is not handler:
                raise ValueError("application_exception_handler_duplicate")
            handlers[error_type] = handler
    routes = list(_http_routes(application.routes))
    for router in routers:
        for route in _http_routes(router.routes):
            methods = getattr(route, "methods", None)
            if not methods or not hasattr(route, "path"):
                raise TypeError("application_route_invalid")
            if any(
                set(methods) & set(getattr(old, "methods", ()) or ()) and _paths_overlap(route, old)
                for old in routes
            ):
                raise ValueError("application_route_collision")
            routes.append(route)
    for router in routers:
        application.include_router(router)
    for error_type, handler in handlers.items():
        application.add_exception_handler(error_type, handler)
