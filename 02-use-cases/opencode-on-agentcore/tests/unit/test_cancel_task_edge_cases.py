# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for cancel_task edge cases.

Validates: Requirements 6.1, 6.2, 6.3

Tests cover:
- Cancel of job not found in DynamoDB returns error
- Cancel of terminal state job (COMPLETE/FAILED/CANCELLED) returns error
- In-process cancellation success skips StopRuntimeSession
- Cross-session fallback when job not in _running_tasks
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from container.code_mcp_server import (
    cancel_task,
    _running_tasks,
    _cancel_flags,
)


# ---------------------------------------------------------------------------
# Test: Job not found in DynamoDB
# ---------------------------------------------------------------------------


class TestCancelTaskJobNotFound:
    """Cancel of a job not found in DynamoDB returns an error."""

    @pytest.mark.asyncio
    async def test_returns_error_when_job_not_in_dynamodb(self):
        """query_job_record returns None → cancel_task returns error.

        Validates: Requirements 6.1, 6.2, 6.3
        """
        async def mock_query_job_record(job_id, user_id):
            return None

        with patch(
            "container.code_mcp_server.query_job_record",
            side_effect=mock_query_job_record,
        ):
            result = await cancel_task(job_id="nonexistent-job", _user_id="user-1")

        assert "error" in result
        assert result["error"] == "Job not found"


# ---------------------------------------------------------------------------
# Test: Terminal state jobs
# ---------------------------------------------------------------------------


class TestCancelTaskTerminalState:
    """Cancel of a terminal state job (COMPLETE/FAILED/CANCELLED) returns error."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("terminal_status", ["COMPLETE", "FAILED", "CANCELLED"])
    async def test_returns_error_for_terminal_state(self, terminal_status):
        """Jobs already in a terminal state cannot be cancelled.

        Validates: Requirements 6.1, 6.2, 6.3
        """
        async def mock_query_job_record(job_id, user_id):
            return {
                "job_id": job_id,
                "status": terminal_status,
                "user_id": user_id,
                "runtime_session_id": "session-123",
            }

        with patch(
            "container.code_mcp_server.query_job_record",
            side_effect=mock_query_job_record,
        ):
            result = await cancel_task(job_id="job-123", _user_id="user-1")

        assert "error" in result
        assert terminal_status in result["error"]
        assert "terminal state" in result["error"]


# ---------------------------------------------------------------------------
# Test: In-process cancellation success skips StopRuntimeSession
# ---------------------------------------------------------------------------


class TestCancelTaskInProcessSuccess:
    """When in-process cancellation succeeds, StopRuntimeSession is skipped."""

    @pytest.mark.asyncio
    async def test_in_process_success_skips_stop_runtime_session(self):
        """If job is in _running_tasks and task.cancel() succeeds,
        StopRuntimeSession must NOT be called.

        Validates: Requirements 6.1, 6.3
        """
        job_id = "in-process-job-1"
        user_id = "user-1"
        stop_session_called = False

        async def mock_query_job_record(job_id, user_id):
            return {
                "job_id": job_id,
                "status": "RUNNING",
                "user_id": user_id,
                "runtime_session_id": "session-abc",
            }

        async def mock_update_job_status(job_id, user_id, status, **kwargs):
            pass

        mock_task = MagicMock()
        mock_task.cancel = MagicMock()  # succeeds without raising

        _running_tasks[job_id] = mock_task
        _cancel_flags[job_id] = False

        mock_boto_client = MagicMock()

        def mock_stop_runtime_session(**kwargs):
            nonlocal stop_session_called
            stop_session_called = True

        mock_boto_client.stop_runtime_session = mock_stop_runtime_session

        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_boto_client

        try:
            with (
                patch(
                    "container.code_mcp_server.query_job_record",
                    side_effect=mock_query_job_record,
                ),
                patch(
                    "container.code_mcp_server.update_job_status",
                    side_effect=mock_update_job_status,
                ),
                patch.dict("sys.modules", {"boto3": mock_boto3}),
                patch("container.code_mcp_server.boto3", mock_boto3, create=True),
            ):
                result = await cancel_task(job_id=job_id, _user_id=user_id)

            # In-process cancel succeeded → StopRuntimeSession NOT called
            assert not stop_session_called, (
                "StopRuntimeSession should not be called when in-process cancel succeeds"
            )
            mock_task.cancel.assert_called_once()
            assert result["status"] == "CANCELLED"
            assert result["job_id"] == job_id

        finally:
            _running_tasks.pop(job_id, None)
            _cancel_flags.pop(job_id, None)


# ---------------------------------------------------------------------------
# Test: Cross-session fallback when job not in _running_tasks
# ---------------------------------------------------------------------------


class TestCancelTaskCrossSessionFallback:
    """When job is not in _running_tasks, StopRuntimeSession is called."""

    @pytest.mark.asyncio
    async def test_cross_session_fallback_when_not_in_running_tasks(self):
        """If job is NOT in _running_tasks, cancel_task falls back to
        StopRuntimeSession and still updates DynamoDB.

        Validates: Requirements 6.2, 6.3
        """
        job_id = "remote-job-1"
        user_id = "user-1"
        session_id = "session-xyz"
        stop_session_calls = []

        async def mock_query_job_record(job_id, user_id):
            return {
                "job_id": job_id,
                "status": "RUNNING",
                "user_id": user_id,
                "runtime_session_id": session_id,
            }

        update_calls = []

        async def mock_update_job_status(job_id, user_id, status, **kwargs):
            update_calls.append({"job_id": job_id, "status": status})

        # Ensure job is NOT in _running_tasks
        _running_tasks.pop(job_id, None)
        _cancel_flags.pop(job_id, None)

        mock_boto_client = MagicMock()

        def mock_stop_runtime_session(**kwargs):
            stop_session_calls.append(kwargs)

        mock_boto_client.stop_runtime_session = mock_stop_runtime_session

        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_boto_client

        try:
            with (
                patch(
                    "container.code_mcp_server.query_job_record",
                    side_effect=mock_query_job_record,
                ),
                patch(
                    "container.code_mcp_server.update_job_status",
                    side_effect=mock_update_job_status,
                ),
                patch(
                    "container.code_mcp_server._get_runtime_arn",
                    return_value="arn:aws:bedrock-agentcore:us-east-1:123:runtime/test-rt",
                ),
                patch.dict("sys.modules", {"boto3": mock_boto3}),
                patch("container.code_mcp_server.boto3", mock_boto3, create=True),
            ):
                result = await cancel_task(job_id=job_id, _user_id=user_id)

            # StopRuntimeSession must have been called
            assert len(stop_session_calls) == 1, (
                f"Expected 1 StopRuntimeSession call, got {len(stop_session_calls)}"
            )
            assert stop_session_calls[0]["runtimeSessionId"] == session_id

            # DynamoDB must still be updated to CANCELLED
            assert len(update_calls) == 1
            assert update_calls[0]["status"] == "CANCELLED"

            assert result["status"] == "CANCELLED"
            assert result["job_id"] == job_id

        finally:
            _running_tasks.pop(job_id, None)
            _cancel_flags.pop(job_id, None)
