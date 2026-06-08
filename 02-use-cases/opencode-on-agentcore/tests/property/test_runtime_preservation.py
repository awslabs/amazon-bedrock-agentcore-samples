# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property tests: Preservation — MCP Protocol Behavior Unchanged.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.6**

Property 2 — Preservation:
  After the bugfix, all existing MCP tool registrations, function signatures,
  FastMCP instance naming, and BedrockAgentCoreApp async task management
  MUST remain unchanged.

  These tests capture the OBSERVED baseline behavior on UNFIXED code.
  They MUST PASS on unfixed code (confirming what we need to preserve)
  and MUST CONTINUE TO PASS after the fix (confirming no regressions).

Observation-first methodology:
  1. FastMCP("opencode") is called → mcp instance exists
  2. 6 tool functions are decorated with @mcp.tool(): code, run_coding_task,
     connect_git_host, get_task_status, list_tasks, cancel_task
  3. BedrockAgentCoreApp instance (app) has add_async_task / complete_async_task
  4. Tool function signatures match expected parameter names
"""

from __future__ import annotations

import inspect


# ── Test 1: OpenCode FastMCP instance exists and is named "opencode" ─────

class TestOpenCodeFastMCPInstance:
    """The unified module must create a FastMCP instance named 'opencode'.

    **Validates: Requirements 3.1**

    Since FastMCP is mocked, we verify the module has an `mcp` attribute
    and that the source code passes "opencode" to FastMCP().
    """

    def test_opencode_fastmcp_named_opencode(self):
        """Module has an mcp attribute and source shows FastMCP('opencode')."""
        import inspect
        import container.code_mcp_server as mod

        # mcp attribute must exist
        assert hasattr(mod, "mcp"), "OpenCode module missing 'mcp' attribute"

        # Verify the source code passes "opencode" to FastMCP
        source = inspect.getsource(mod)
        assert 'FastMCP("opencode")' in source or "FastMCP('opencode')" in source, (
            "FastMCP('opencode') not found in source — "
            "the unified MCP server instance is not named 'opencode'"
        )


# ── Test 2: Unified server has 6 registered tool functions ───────────────

class TestOpenCodeToolCount:
    """The unified module must define all 6 tool functions.

    **Validates: Requirements 3.1, 3.2**

    Since @mcp.tool() returns lambda fn: fn (mock), the decorated
    functions exist as module-level callables.
    """

    def test_opencode_has_all_tools(self):
        """All expected tool functions are importable and callable."""
        import container.code_mcp_server as mod

        expected_tools = [
            "code",
            "run_coding_task",
            "connect_git_host",
            "get_task_status",
            "list_tasks",
            "cancel_task",
        ]

        for tool_name in expected_tools:
            assert hasattr(mod, tool_name), (
                f"Missing tool function: {tool_name}"
            )
            fn = getattr(mod, tool_name)
            assert callable(fn), (
                f"Tool {tool_name} is not callable"
            )


# ── Test 3: OpenCode BedrockAgentCoreApp has async task methods ──────────

class TestOpenCodeAsyncTaskManagement:
    """The OpenCode app (BedrockAgentCoreApp) must expose add_async_task
    and complete_async_task methods.

    **Validates: Requirements 3.3, 3.4**
    """

    def test_app_has_async_task_methods(self):
        """app.add_async_task and app.complete_async_task are callable."""
        from container.code_mcp_server import app

        assert callable(app.add_async_task), (
            "app.add_async_task is not callable"
        )
        assert callable(app.complete_async_task), (
            "app.complete_async_task is not callable"
        )


# ── Test 4: Unified server tool function signatures are preserved ────────

class TestOpenCodeToolSignatures:
    """Tool function parameter names must match the expected signatures.

    **Validates: Requirements 3.1, 3.6**

    This ensures the fix doesn't accidentally alter function signatures,
    which would break MCP tool schema generation and client compatibility.
    """

    def test_code_signature(self):
        """code() has the expected parameters."""
        from container.code_mcp_server import code

        params = list(inspect.signature(code).parameters.keys())
        expected = [
            "task_description", "repo_url", "base_branch",
            "target_branch", "timeout_minutes", "_user_id", "ctx",
        ]
        assert params == expected, (
            f"code() signature mismatch: {params} != {expected}"
        )

    def test_run_coding_task_signature(self):
        """run_coding_task() has the expected parameters."""
        from container.code_mcp_server import run_coding_task

        params = list(inspect.signature(run_coding_task).parameters.keys())
        expected = [
            "task_description", "repo_url", "base_branch",
            "target_branch", "timeout_minutes", "_user_id", "ctx",
        ]
        assert params == expected, (
            f"run_coding_task() signature mismatch: {params} != {expected}"
        )

    def test_connect_git_host_signature(self):
        """connect_git_host() has the expected parameters."""
        from container.code_mcp_server import connect_git_host

        params = list(inspect.signature(connect_git_host).parameters.keys())
        expected = ["git_host", "_user_id", "ctx"]
        assert params == expected, (
            f"connect_git_host() signature mismatch: {params} != {expected}"
        )

    def test_get_task_status_signature(self):
        """get_task_status() has the expected parameters."""
        from container.code_mcp_server import get_task_status

        params = list(inspect.signature(get_task_status).parameters.keys())
        expected = ["job_id", "_user_id"]
        assert params == expected, (
            f"get_task_status() signature mismatch: {params} != {expected}"
        )

    def test_list_tasks_signature(self):
        """list_tasks() has the expected parameters."""
        from container.code_mcp_server import list_tasks

        params = list(inspect.signature(list_tasks).parameters.keys())
        expected = ["status", "limit", "_user_id"]
        assert params == expected, (
            f"list_tasks() signature mismatch: {params} != {expected}"
        )

    def test_cancel_task_signature(self):
        """cancel_task() has the expected parameters."""
        from container.code_mcp_server import cancel_task

        params = list(inspect.signature(cancel_task).parameters.keys())
        expected = ["job_id", "_user_id"]
        assert params == expected, (
            f"cancel_task() signature mismatch: {params} != {expected}"
        )
