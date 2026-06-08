# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Integration test: ``cancel_task`` for running async tasks.

Tests cross-session cancellation (StopRuntimeSession) path.
After runtime consolidation (spec 13), cancel_task lives in the unified
container/code_mcp_server.py alongside all other tools.

Requirements: 7.2, 7.5
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub external dependencies
# ---------------------------------------------------------------------------
fastmcp_mock = MagicMock()
fastmcp_mock.FastMCP.return_value.tool.return_value = lambda fn: fn
sys.modules.setdefault("fastmcp", fastmcp_mock)

agentcore_mock = MagicMock()
agentcore_mock.BedrockAgentCoreApp.return_value = MagicMock()
sys.modules.setdefault("bedrock_agentcore", agentcore_mock)
sys.modules.setdefault("bedrock_agentcore.runtime", agentcore_mock)

strands_mock = MagicMock()
strands_mock.tool = lambda fn: fn
sys.modules.setdefault("strands", strands_mock)

from container.code_mcp_server import (  # noqa: E402
    cancel_task,
)


class TestCancelTaskCrossSession:
    """Cross-session cancellation: task on a different microVM (Req 7.2, 7.5)."""

    @pytest.mark.asyncio
    async def test_cross_session_calls_stop_runtime_session(self):
        """Verify StopRuntimeSession called with correct session_id."""
        job_id = "job-cross-1"

        fake_record = {
            "job_id": job_id,
            "status": "RUNNING",
            "user_id": "user-1",
            "runtime_session_id": "sess-xyz-123",
        }

        mock_boto_client = MagicMock()

        with (
            patch(
                "container.code_mcp_server.query_job_record",
                new_callable=AsyncMock,
                return_value=fake_record,
            ),
            patch(
                "container.code_mcp_server.update_job_status",
                new_callable=AsyncMock,
            ) as mock_update,
            patch(
                "container.code_mcp_server._get_runtime_arn",
                return_value="arn:aws:bedrock-agentcore:us-east-1:123:runtime/rt-test",
            ),
            patch("boto3.client", return_value=mock_boto_client),
        ):
            result = await cancel_task(job_id=job_id, _user_id="user-1")

        assert result["status"] == "CANCELLED"
        mock_boto_client.stop_runtime_session.assert_called_once()
        call_kwargs = mock_boto_client.stop_runtime_session.call_args
        assert call_kwargs.kwargs.get("runtimeSessionId") == "sess-xyz-123" or \
               (call_kwargs[1] if len(call_kwargs) > 1 else {}).get("runtimeSessionId") == "sess-xyz-123"

    @pytest.mark.asyncio
    async def test_cross_session_still_updates_ddb_on_stop_failure(self):
        """Verify DDB updated to CANCELLED even if StopRuntimeSession fails (Req 7.5)."""
        job_id = "job-cross-fail-1"

        fake_record = {
            "job_id": job_id,
            "status": "RUNNING",
            "user_id": "user-1",
            "runtime_session_id": "sess-dead",
        }

        mock_boto_client = MagicMock()
        mock_boto_client.stop_runtime_session.side_effect = RuntimeError("session gone")

        with (
            patch(
                "container.code_mcp_server.query_job_record",
                new_callable=AsyncMock,
                return_value=fake_record,
            ),
            patch(
                "container.code_mcp_server.update_job_status",
                new_callable=AsyncMock,
            ) as mock_update,
            patch(
                "container.code_mcp_server._get_runtime_arn",
                return_value="arn:aws:bedrock-agentcore:us-east-1:123:runtime/rt-test",
            ),
            patch("boto3.client", return_value=mock_boto_client),
        ):
            result = await cancel_task(job_id=job_id, _user_id="user-1")

        # Still CANCELLED despite StopRuntimeSession failure
        assert result["status"] == "CANCELLED"
        mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_terminal_state_returns_error(self):
        """Verify cancelling a COMPLETE job returns error (Req 7.3)."""
        job_id = "job-done-1"

        with patch(
            "container.code_mcp_server.query_job_record",
            new_callable=AsyncMock,
            return_value={"job_id": job_id, "status": "COMPLETE", "user_id": "user-1"},
        ):
            result = await cancel_task(job_id=job_id, _user_id="user-1")

        assert "error" in result
        assert "terminal" in result["error"].lower()
