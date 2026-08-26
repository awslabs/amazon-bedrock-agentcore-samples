"""The shared Lambda-target entry point.

Every tool family's handler is `dispatch(event, context, TOOLS)`. Extracting it once
means the tenant check, the log binding, and the error translation cannot be
forgotten in tool number nine — which is the realistic failure once a catalog grows to a
dozen tool families.

**What the Gateway sends.** A Lambda target receives the tool's arguments as the
bare event body, with the tool *name* out of band in the Lambda client context.
Nothing in the event says which tenant is calling; that arrives in headers the
interceptor injected.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .context import RequestContext, tenant_context, tool_arguments, tool_name
from .errors import BackendError, MissingIdentityError, ToolError
from .observability import (
    bind_request_context,
    clear_request_context,
    count,
    log_decision,
    log_refusal,
    logger,
)
from .response import refusal

ToolFn = Callable[[dict[str, Any], RequestContext], dict[str, Any]]


def dispatch(event: dict[str, Any], context: Any, tools: dict[str, ToolFn]) -> dict[str, Any]:
    """Route one Gateway invocation to the right tool function.

    Returns a response envelope in every path, including failures: a tool that
    raises produces a transport error the model cannot reason about, whereas a
    `{message}` is something it can relay to the user.
    """
    name = tool_name(context)

    try:
        request = tenant_context(context)
    except MissingIdentityError:
        # Not a refusal the model should soften — the identity chain is broken, so
        # log it as an error and return something honest without any data in it.
        logger.exception("tool invoked without verified identity", tool=name)
        count("ToolIdentityFailures", tool=name or "unknown")
        return refusal("I can't verify who this request is for, so I won't return any travel data.")

    bind_request_context(**request.log_fields, tool=name or "unknown")

    try:
        if name is None or name not in tools:
            # A tool the Gateway routed here but this family does not implement
            # means the target and the code have drifted apart.
            log_refusal("unknown tool routed to this handler", requested=name)
            return refusal("That capability isn't available.")

        arguments = tool_arguments(event)

        # Arguments are logged by *shape*, never by value: a search argument can
        # carry a traveller's name, and a name must never reach a log line.
        log_decision("tool invoked", arguments=sorted(arguments))

        result = tools[name](arguments, request)
        count("ToolInvocations", tool=name)
        return result

    except BackendError as error:
        # Distinguish "the backend says no such thing" from "the backend is broken":
        # the first is an answer, the second is a fault the model must not dress up
        # as one.
        if error.status == 404:
            log_refusal("backend has no such resource", status=error.status)
            return refusal("I couldn't find that.")
        logger.exception("backend call failed", tool=name, status=error.status)
        count("ToolBackendErrors", tool=name or "unknown")
        return refusal("I couldn't reach the travel system just now, so I'd rather not guess.")

    except ToolError as error:
        log_refusal("tool refused", reason=str(error))
        return refusal(str(error))

    except Exception:
        # Never let a stack trace become model context. The traceback goes to logs
        # where an operator can find it; the model gets a sentence.
        logger.exception("unhandled tool failure", tool=name)
        count("ToolUnhandledErrors", tool=name or "unknown")
        return refusal("Something went wrong on my side. I haven't changed anything.")

    finally:
        # Containers are reused, so unbound keys would attribute the next request to
        # this one's tenant.
        clear_request_context()
