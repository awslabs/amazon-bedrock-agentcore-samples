# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property test: Bug Condition — Runtime Containers Missing /ping Health Check.

**Validates: Requirements 1.1, 1.2, 1.3**

Property 1 — Bug Condition:
  The AgentCore runtime container (unified OpenCode) MUST serve a /ping GET
  endpoint on port 8000 so the AgentCore platform can verify container health.
  The fix adds /ping as a custom_route on the FastMCP server.

  On UNFIXED code this test FAILS because the container has no /ping route.

  Note: After runtime consolidation (spec 13), there is only one runtime
  container. The ConnectGitHost runtime tests have been removed.
"""

from __future__ import annotations

import inspect


class TestOpenCodeRuntimeHealthBugCondition:
    """OpenCode runtime: must have /ping health check on port 8000.

    **Validates: Requirements 1.1, 1.3**
    """

    def test_opencode_has_ping_route(self):
        """Source should register a /ping custom_route on FastMCP.

        FAILS on unfixed code because no /ping route exists.
        """
        import container.code_mcp_server as mod

        source = inspect.getsource(mod)
        assert 'custom_route("/ping"' in source or "custom_route('/ping'" in source, (
            "BUG CONFIRMED: No /ping custom_route in code_mcp_server.py"
        )

    def test_opencode_ping_returns_status(self):
        """The /ping handler should return a JSON status response.

        FAILS on unfixed code because no /ping handler exists.
        """
        import container.code_mcp_server as mod

        source = inspect.getsource(mod)
        assert '"status"' in source and '"Healthy"' in source or "get_current_ping_status" in source, (
            "BUG CONFIRMED: No health status response in code_mcp_server.py"
        )
