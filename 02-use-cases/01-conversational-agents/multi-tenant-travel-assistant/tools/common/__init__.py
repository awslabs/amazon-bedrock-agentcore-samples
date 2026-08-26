"""Shared plumbing for every tool family.

Deliberately thin: identity extraction, the backend client, the response envelope,
logging, and the dispatch loop. Anything that reasons about *travel* belongs to a
tool family, not here — this package exists so the tenant check and the error
translation are written once rather than thirteen times.
"""

from .authz import AmbiguousTravelerError, ensure_can_act_for, resolve_target_traveler
from .backend import get, post
from .context import RequestContext, backend_url, tenant_context, tool_arguments, tool_name
from .errors import BackendError, MissingIdentityError, ToolError
from .handler import dispatch
from .observability import (
    bind_request_context,
    count,
    log_decision,
    log_refusal,
    logger,
    observe,
)
from .response import refusal, tool_response

__all__ = [
    "AmbiguousTravelerError",
    "BackendError",
    "MissingIdentityError",
    "RequestContext",
    "ToolError",
    "backend_url",
    "bind_request_context",
    "count",
    "dispatch",
    "ensure_can_act_for",
    "get",
    "post",
    "log_decision",
    "log_refusal",
    "logger",
    "observe",
    "refusal",
    "resolve_target_traveler",
    "tenant_context",
    "tool_arguments",
    "tool_name",
    "tool_response",
]
