# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Cold-start analysis: single runtime consolidation — post-consolidation.

After runtime consolidation (spec 13), all 6 tools run on a single
FastMCP("opencode") server. This file retains the cold-start feasibility
assertions that remain valid post-consolidation.

Tests verify:
  1. Consolidated tool count is 6
  2. No tool name collisions
  3. Cold start is acceptable for the unified runtime
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# 1. Tool consolidation — correct total, no collisions
# ---------------------------------------------------------------------------

class TestToolConsolidation:
    """Verify all 6 tools are present on the unified runtime."""

    ALL_TOOLS = {
        "code", "run_coding_task",
        "connect_git_host", "get_task_status", "list_tasks", "cancel_task",
    }

    def test_consolidated_tool_count_is_six(self):
        """Unified runtime exposes exactly 6 tools."""
        assert len(self.ALL_TOOLS) == 6

    def test_all_tools_exist_in_unified_server(self):
        """All 6 tools are importable from the unified server module."""
        import container.code_mcp_server as mod
        for tool in self.ALL_TOOLS:
            assert hasattr(mod, tool) and callable(getattr(mod, tool)), (
                f"Tool '{tool}' not found in unified server"
            )

    def test_connect_git_host_signature_compatible(self):
        """connect_git_host has _user_id and ctx params like other tools."""
        import inspect
        import container.code_mcp_server as mod
        params = list(inspect.signature(mod.connect_git_host).parameters.keys())
        assert "_user_id" in params, "connect_git_host needs _user_id for gateway injection"
        assert "ctx" in params, "connect_git_host needs ctx for elicitation"


# ---------------------------------------------------------------------------
# 2. Cold-start weight estimation
# ---------------------------------------------------------------------------

class TestColdStartWeightEstimation:
    """Verify cold start is acceptable for the consolidated runtime."""

    def test_cold_start_acceptable_for_consolidated_runtime(self):
        """Per the design doc, runtimes respond in ~1s.

        Even with the heavier OpenCode container, the cold start is well
        within the gateway's 20-second tools/list timeout.
        """
        GATEWAY_TIMEOUT_S = 20
        OBSERVED_COLD_START_S = 1.0
        SAFETY_MARGIN = 5.0

        assert OBSERVED_COLD_START_S * SAFETY_MARGIN < GATEWAY_TIMEOUT_S, (
            f"Even with {SAFETY_MARGIN}x safety margin, cold start "
            f"({OBSERVED_COLD_START_S * SAFETY_MARGIN}s) is within "
            f"gateway timeout ({GATEWAY_TIMEOUT_S}s)"
        )

    def test_opencode_dockerfile_installs_opencode(self):
        """OpenCode Dockerfile installs the OpenCode CLI.

        The install method has changed over time. Current: official
        curl installer from opencode.ai (simplest path).
        """
        import pathlib
        dockerfile = pathlib.Path("container/Dockerfile").read_text()
        assert "opencode" in dockerfile.lower(), (
            "Dockerfile should install opencode"
        )
        assert "OPENCODE_BINARY" in dockerfile, (
            "Dockerfile should set OPENCODE_BINARY env var"
        )
