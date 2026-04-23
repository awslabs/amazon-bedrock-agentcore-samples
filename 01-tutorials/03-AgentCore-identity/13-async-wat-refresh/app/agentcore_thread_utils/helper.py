"""ThreadTaskManager — handles threaded async tasks with WAT propagation via copy_context."""

import contextvars
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

from bedrock_agentcore.runtime import BedrockAgentCoreApp, BedrockAgentCoreContext

logger = logging.getLogger("agentcore_thread_utils.helper")

DEFAULT_REFRESH_TIMEOUT = 300  # 5 minutes
DEFAULT_RESULT_TTL = 3600  # 1 hour


class ThreadTaskManager:
    """Manages threaded tasks with WAT propagation and refresh coordination.

    Uses contextvars.copy_context() to propagate the WAT to threads,
    and threading.Event for refresh coordination.

    Args:
        app: BedrockAgentCoreApp instance.
        refresh_timeout: Seconds to wait for a WAT refresh before failing (default: 300).
        result_ttl: Seconds to keep completed results before cleanup (default: 3600).
    """

    def __init__(
        self,
        app: BedrockAgentCoreApp,
        refresh_timeout: int = DEFAULT_REFRESH_TIMEOUT,
        result_ttl: int = DEFAULT_RESULT_TTL,
    ):
        self.app = app
        self.refresh_timeout = refresh_timeout
        self.result_ttl = result_ttl
        self._tasks: Dict[int, dict] = {}
        self._results: Dict[int, dict] = {}
        self._lock = threading.Lock()
        self._registered_task: Optional[Callable] = None
        self._custom_actions: Dict[str, Callable] = {}

    def start(self, task_func: Callable, **kwargs) -> int:
        """Start a threaded task with WAT propagation via copy_context.

        task_func: a function that accepts task_id as first keyword argument.
        Returns the task_id for tracking.
        """
        task_id = self.app.add_async_task("thread_task", {})

        with self._lock:
            self._tasks[task_id] = {
                "event": threading.Event(),
                "wat": None,
                "needs_refresh": False,
            }

        ctx = contextvars.copy_context()

        def _wrapped():
            try:
                result = task_func(task_id=task_id, **kwargs)
                with self._lock:
                    self._results[task_id] = {
                        "status": "completed",
                        "result": result,
                        "completed_at": time.time(),
                    }
            except TimeoutError as e:
                logger.warning(f"[Task {task_id}] {e}")
                with self._lock:
                    self._results[task_id] = {
                        "status": "failed",
                        "error": str(e),
                        "completed_at": time.time(),
                    }
            except Exception as e:
                error_msg = str(e)
                if "expired" in error_msg.lower():
                    logger.warning(f"[Task {task_id}] WAT expired and refresh failed: {error_msg}")
                else:
                    logger.error(f"[Task {task_id}] Failed: {error_msg}", exc_info=True)
                with self._lock:
                    self._results[task_id] = {
                        "status": "failed",
                        "error": error_msg,
                        "completed_at": time.time(),
                    }
            finally:
                with self._lock:
                    self._tasks.pop(task_id, None)
                self.app.complete_async_task(task_id)

        threading.Thread(target=ctx.run, args=(_wrapped,), daemon=True).start()
        return task_id

    def wait_for_wat_refresh(self, task_id: int) -> str:
        """Called by the decorator when WAT expires. Blocks until client refreshes.

        Returns the fresh WAT.
        Raises TimeoutError if no refresh arrives within refresh_timeout.
        """
        with self._lock:
            task_state = self._tasks.get(task_id)
        if not task_state:
            raise RuntimeError(f"Task {task_id} not found")

        task_state["needs_refresh"] = True
        task_state["event"].clear()
        logger.info(
            f"[Task {task_id}] WAT expired. Waiting for client refresh "
            f"(timeout: {self.refresh_timeout}s)... "
            f'Client should send {{"action":"refresh"}} with a fresh JWT to unblock.'
        )

        signaled = task_state["event"].wait(timeout=self.refresh_timeout)
        if not signaled:
            task_state["needs_refresh"] = False
            raise TimeoutError(
                f"WAT refresh timeout after {self.refresh_timeout}s for task {task_id}. "
                'Client did not send {"action":"refresh"} with a fresh JWT in time. '
                "Task will be marked as failed."
            )

        new_wat = task_state["wat"]
        task_state["needs_refresh"] = False
        logger.info(f"[Task {task_id}] WAT refreshed.")
        return new_wat

    def _cleanup_old_results(self):
        """Remove results older than result_ttl."""
        now = time.time()
        expired = [
            tid for tid, res in self._results.items()
            if now - res.get("completed_at", now) > self.result_ttl
        ]
        for tid in expired:
            del self._results[tid]

    def handle_action(self, action: str, payload: dict) -> Optional[dict]:
        """Handle status/refresh/result actions. Returns response dict or None."""

        if action == "status":
            task_info = self.app.get_async_task_info()
            ping_status = self.app.get_current_ping_status()
            with self._lock:
                self._cleanup_old_results()
                needs_refresh = {
                    tid: state["needs_refresh"]
                    for tid, state in self._tasks.items()
                    if state["needs_refresh"]
                }
                completed = {
                    tid: res["status"] for tid, res in self._results.items()
                }
            return {
                "ping_status": ping_status.value,
                "active_tasks": task_info["active_count"],
                "tasks_needing_refresh": needs_refresh,
                "completed_results": completed,
            }

        elif action == "refresh":
            new_wat = BedrockAgentCoreContext.get_workload_access_token()
            if not new_wat:
                return {"status": "error", "message": "No WAT in current context"}

            task_id = payload.get("task_id")
            with self._lock:
                if task_id and task_id in self._tasks:
                    self._tasks[task_id]["wat"] = new_wat
                    self._tasks[task_id]["event"].set()
                    return {"status": "wat_refreshed", "task_id": task_id}
                else:
                    refreshed = []
                    for tid, state in self._tasks.items():
                        if state["needs_refresh"]:
                            state["wat"] = new_wat
                            state["event"].set()
                            refreshed.append(tid)
                    return {"status": "wat_refreshed", "tasks_refreshed": refreshed}

        elif action == "result":
            task_id = payload.get("task_id")
            with self._lock:
                if task_id and task_id in self._results:
                    res = self._results[task_id].copy()
                    res.pop("completed_at", None)
                    return res
                return {
                    "error": "Task not found or still running",
                    "available": list(self._results.keys()),
                }

        return None

    def register_task(self, task_func: Callable):
        """Register the main async task function."""
        self._registered_task = task_func

    def register_action(self, action_name: str, handler: Callable):
        """Register a custom action handler (e.g., 'chat')."""
        self._custom_actions[action_name] = handler

    def handle(self, payload: dict, context=None) -> dict:
        """Handle all actions in one call. Use as the entrypoint body.

        Routes: start, status, refresh, result, custom actions, or returns available actions.
        """
        action = payload.get("action")

        response = self.handle_action(action, payload)
        if response is not None:
            return response

        if action == "start":
            if not self._registered_task:
                return {"error": "No task registered. Call manager.register_task() first."}
            task_id = self.start(self._registered_task)
            return {
                "task_id": task_id,
                "status": "started",
                "message": "If WAT expires, send {\"action\":\"refresh\"} with a fresh JWT.",
            }

        if action in self._custom_actions:
            return self._custom_actions[action](payload, context)

        available = ["start", "status", "refresh", "result"] + list(self._custom_actions.keys())
        return {"available_actions": available}
