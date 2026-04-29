# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Root conftest — stub external dependencies before any test imports.

The container modules (code_mcp_server, tools) depend on ``fastmcp``,
``bedrock_agentcore``, and ``strands`` which are not installed in the
test environment.  We inject lightweight mocks into ``sys.modules``
so that ``import`` statements succeed regardless of test ordering.

We also ensure that ``container.code_mcp_server`` is imported exactly
once with the correct stubs, preventing test-ordering issues where a
force-reimport in one test file creates a different module object than
what other tests patch against.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stub fastmcp
# ---------------------------------------------------------------------------
_fastmcp_mock = MagicMock()
_fastmcp_mock.FastMCP.return_value.tool.return_value = lambda fn: fn
sys.modules["fastmcp"] = _fastmcp_mock

# ---------------------------------------------------------------------------
# Stub bedrock_agentcore
# ---------------------------------------------------------------------------
_agentcore_mock = MagicMock()
_agentcore_mock.BedrockAgentCoreApp.return_value = MagicMock()
sys.modules["bedrock_agentcore"] = _agentcore_mock
sys.modules["bedrock_agentcore.runtime"] = _agentcore_mock

# ---------------------------------------------------------------------------
# Stub strands
# ---------------------------------------------------------------------------
_strands_mock = MagicMock()
_strands_mock.tool = lambda fn: fn
sys.modules["strands"] = _strands_mock

# ---------------------------------------------------------------------------
# Alias bare "lib" to "container.lib" so that
# `from lib.dynamodb_helpers import ...` resolves correctly when the
# module is reloaded from the test runner.
# Inside the container, "lib" is on sys.path; in tests we need the alias.
# ---------------------------------------------------------------------------
import container.lib as _container_lib
import container.lib.dynamodb_helpers as _container_ddb

sys.modules["lib"] = _container_lib
sys.modules["lib.dynamodb_helpers"] = _container_ddb
