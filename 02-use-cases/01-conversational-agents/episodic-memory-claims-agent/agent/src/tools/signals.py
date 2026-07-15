"""
Per-session investigation signals collector (Phase 3.1).

The investigation tools already compute structured facts (policy status,
coverage determination, fraud score + flags, claims history). This collector
captures those structured results at the source, keyed by ``session_id``, so
``/invoke`` can persist a review task from real data instead of regex-parsing
the agent's free-text closing message (brittle, wording drifts).

Design notes
------------
- In-process and decoupled from AWS: tools call ``record(...)`` as a side
  effect; no DynamoDB / IAM needed in the tool layer (easy to unit-test).
- Thread-safe: the Flask dev server runs ``threaded=True``, so concurrent
  claims must not clobber each other's signals.
- Latest-write-wins per tool: if a tool is called more than once in a single
  investigation, the most recent structured result is kept.

LIMITATION (tracked in HITL_IMPLEMENTATION.md, Phase 3 Open Q): this store is
in-process. When the system moves to AgentCore Runtime / Lambda (multi-process),
the collector must become external (e.g. a scratch store keyed by session, or
the task record itself). In-process is fine for the local demo.
"""

import threading
from typing import Any

# session_id -> { tool_name: structured_result }
_signals: dict[str, dict[str, Any]] = {}
_lock = threading.Lock()


def record(session_id: str, tool_name: str, structured_result: dict) -> None:
    """Record a tool's structured result for a session (latest-write-wins).

    Args:
        session_id: The claim/session this signal belongs to (from agent state).
        tool_name: Logical name of the investigation tool (e.g. "policy",
            "claims_history", "fraud", "coverage").
        structured_result: The structured facts the tool computed.
    """
    if not session_id:
        return
    with _lock:
        _signals.setdefault(session_id, {})[tool_name] = structured_result


def get(session_id: str) -> dict[str, Any]:
    """Return a copy of all recorded signals for a session.

    Returns a dict of ``{tool_name: structured_result}``. Empty dict if nothing
    has been recorded for the session.
    """
    with _lock:
        return dict(_signals.get(session_id, {}))


def clear(session_id: str) -> None:
    """Drop all recorded signals for a session (call after persisting a task)."""
    with _lock:
        _signals.pop(session_id, None)


# ---------------------------------------------------------------------------
# Subtool trace writer — writes tool call details to subtools/ namespace
# for observability in the admin memory inspector.
# ---------------------------------------------------------------------------
import json
import logging

_trace_logger = logging.getLogger("claims-demo.signals.trace")

_trace_client = None
_trace_memory_id = None


def configure_trace(memory_client, memory_id: str) -> None:
    """Set up the subtool trace writer with a memory client and ID.

    Called once by the investigation/adjudication agent factories when mode=auto.
    """
    global _trace_client, _trace_memory_id
    _trace_client = memory_client
    _trace_memory_id = memory_id


def write_subtool_trace(session_id: str, tool_name: str, input_summary: str, output_summary: str) -> None:
    """Write a trace event to the subtools namespace for a tool call.

    Args:
        session_id: The claim session this belongs to.
        tool_name: Name of the tool (e.g. "lookup_policy").
        input_summary: Brief description of what was passed in.
        output_summary: Brief description of what came back.
    """
    if not _trace_client or not _trace_memory_id or not session_id:
        return
    try:
        trace_text = json.dumps({
            "tool": tool_name,
            "query": input_summary,
            "filter": "n/a",
            "result_count": 1,
            "results": [output_summary],
        })
        _trace_client.create_event(
            memory_id=_trace_memory_id,
            actor_id="system",
            session_id=session_id,
            messages=[(trace_text, "TOOL")],
        )
    except Exception as e:
        _trace_logger.warning("Failed to write subtool trace: %s", e)
