"""with_wat_refresh — thread-safe drop-in replacement for @requires_access_token."""

import logging
import threading
from functools import wraps
from typing import Any, Callable, List, Literal, Optional

from bedrock_agentcore.runtime import BedrockAgentCoreContext
from bedrock_agentcore.identity.auth import requires_access_token

logger = logging.getLogger("agentcore_thread_utils.decorator")

# Thread-local storage for task context — safe for concurrent tasks
_local = threading.local()


def set_task_context(manager, task_id: int):
    """Set the current task context for WAT refresh coordination.

    Must be called at the start of each task function.
    Uses thread-local storage so concurrent tasks don't interfere.
    """
    _local.task_manager = manager
    _local.task_id = task_id


def _get_task_context():
    """Get the current task context from thread-local storage."""
    manager = getattr(_local, "task_manager", None)
    task_id = getattr(_local, "task_id", None)
    return manager, task_id


def with_wat_refresh(
    *,
    provider_name: str,
    scopes: List[str],
    auth_flow: Literal["M2M", "USER_FEDERATION"] = "M2M",
    into: str = "access_token",
    on_auth_url: Optional[Callable] = None,
    callback_url: Optional[str] = None,
    force_authentication: bool = False,
    max_retries: int = 2,
) -> Callable:
    """Decorator that wraps @requires_access_token with WAT refresh for threads.

    Same interface as @requires_access_token but handles WAT expiration
    by pausing the thread and waiting for a client refresh.

    Args:
        max_retries: Maximum number of refresh attempts before giving up (default: 2).
    """

    def decorator(func: Callable) -> Callable:
        @requires_access_token(
            provider_name=provider_name,
            scopes=scopes,
            auth_flow=auth_flow,
            into=into,
            on_auth_url=on_auth_url,
            callback_url=callback_url,
            force_authentication=force_authentication,
        )
        def _inner_call(*, access_token: str):
            return func(access_token=access_token)

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            manager, task_id = _get_task_context()
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    return _inner_call(**kwargs)
                except Exception as e:
                    last_error = e
                    if "expired" in str(e).lower() and manager and task_id:
                        if attempt < max_retries:
                            logger.info(
                                f"WAT expired (attempt {attempt + 1}/{max_retries}). "
                                f"Requesting refresh for task {task_id}..."
                            )
                            new_wat = manager.wait_for_wat_refresh(task_id)
                            BedrockAgentCoreContext.set_workload_access_token(new_wat)
                            logger.info("WAT refreshed. Retrying...")
                        else:
                            logger.error(f"WAT expired after {max_retries} refresh attempts.")
                            raise
                    else:
                        raise

            raise last_error

        return wrapper

    return decorator
