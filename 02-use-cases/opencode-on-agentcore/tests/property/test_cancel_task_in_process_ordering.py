# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property test: in-process cancellation is attempted before cross-session fallback.

Feature: 13-runtime-consolidation
Property 2: In-process cancellation is attempted before cross-session fallback

For any job_id that exists in the in-process _running_tasks registry,
calling cancel_task SHALL attempt to cancel the asyncio task before making
a StopRuntimeSession API call. If the job_id is NOT in _running_tasks,
cancel_task SHALL proceed directly to StopRuntimeSession.

Validates: Requirements 6.1, 6.2
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from container.code_mcp_server import (
    cancel_task,
    _running_tasks,
    _cancel_flags,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
job_id_st = st.uuids().map(str)
user_id_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=40,
)
session_id_st = st.text(min_size=1, max_size=50)


class TestCancelTaskInProcessOrdering:
    """**Feature: 13-runtime-consolidation, Property 2: In-process cancellation is attempted before cross-session fallback**"""

    @given(
        job_id=job_id_st,
        user_id=user_id_st,
        session_id=session_id_st,
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_in_process_cancel_attempted_before_stop_session(
        self, job_id, user_id, session_id
    ):
        """**Validates: Requirements 6.1, 6.2**

        When job_id IS in _running_tasks, asyncio task.cancel() must be
        called and StopRuntimeSession must NOT be called (assuming
        in-process cancel succeeds).
        """
        call_order = []

        async def mock_query_job_record(job_id, user_id):
            return {
                "job_id": job_id,
                "status": "RUNNING",
                "user_id": user_id,
                "runtime_session_id": session_id,
            }

        async def mock_update_job_status(job_id, user_id, status, **kwargs):
            pass

        mock_task = MagicMock()

        def mock_cancel():
            call_order.append("task.cancel")

        mock_task.cancel = mock_cancel

        # Place job in _running_tasks so in-process path is taken
        _running_tasks[job_id] = mock_task
        _cancel_flags[job_id] = False

        mock_boto_client = MagicMock()

        def mock_stop_runtime_session(**kwargs):
            call_order.append("StopRuntimeSession")

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

            # task.cancel() must have been called
            assert "task.cancel" in call_order, (
                f"Expected task.cancel to be called, got: {call_order}"
            )
            # StopRuntimeSession must NOT have been called (in-process succeeded)
            assert "StopRuntimeSession" not in call_order, (
                f"StopRuntimeSession should not be called when in-process cancel succeeds, got: {call_order}"
            )
            assert result["status"] == "CANCELLED"

        finally:
            _running_tasks.pop(job_id, None)
            _cancel_flags.pop(job_id, None)

    @given(
        job_id=job_id_st,
        user_id=user_id_st,
        session_id=session_id_st,
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_stop_session_called_directly_when_not_in_running_tasks(
        self, job_id, user_id, session_id
    ):
        """**Validates: Requirements 6.1, 6.2**

        When job_id is NOT in _running_tasks, StopRuntimeSession must be
        called directly without any asyncio task.cancel() attempt.
        """
        call_order = []

        async def mock_query_job_record(job_id, user_id):
            return {
                "job_id": job_id,
                "status": "RUNNING",
                "user_id": user_id,
                "runtime_session_id": session_id,
            }

        async def mock_update_job_status(job_id, user_id, status, **kwargs):
            pass

        # Ensure job is NOT in _running_tasks
        _running_tasks.pop(job_id, None)
        _cancel_flags.pop(job_id, None)

        mock_boto_client = MagicMock()

        def mock_stop_runtime_session(**kwargs):
            call_order.append("StopRuntimeSession")

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
                    return_value="arn:aws:bedrock-agentcore:us-east-1:123:runtime/rt-test",
                ),
                patch.dict("sys.modules", {"boto3": mock_boto3}),
                patch("container.code_mcp_server.boto3", mock_boto3, create=True),
            ):
                result = await cancel_task(job_id=job_id, _user_id=user_id)

            # StopRuntimeSession must have been called directly
            assert "StopRuntimeSession" in call_order, (
                f"Expected StopRuntimeSession to be called when job not in _running_tasks, got: {call_order}"
            )
            assert result["status"] == "CANCELLED"

        finally:
            _running_tasks.pop(job_id, None)
            _cancel_flags.pop(job_id, None)

    @given(
        job_id=job_id_st,
        user_id=user_id_st,
        session_id=session_id_st,
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_fallback_to_stop_session_when_in_process_cancel_fails(
        self, job_id, user_id, session_id
    ):
        """**Validates: Requirements 6.1, 6.2**

        When job_id IS in _running_tasks but task.cancel() raises an
        exception, cancel_task must fall back to StopRuntimeSession.
        This verifies the ordering: in-process attempted first, then
        cross-session fallback on failure.
        """
        call_order = []

        async def mock_query_job_record(job_id, user_id):
            return {
                "job_id": job_id,
                "status": "RUNNING",
                "user_id": user_id,
                "runtime_session_id": session_id,
            }

        async def mock_update_job_status(job_id, user_id, status, **kwargs):
            pass

        mock_task = MagicMock()

        def mock_cancel():
            call_order.append("task.cancel")
            raise Exception("task already done")

        mock_task.cancel = mock_cancel

        _running_tasks[job_id] = mock_task
        _cancel_flags[job_id] = False

        mock_boto_client = MagicMock()

        def mock_stop_runtime_session(**kwargs):
            call_order.append("StopRuntimeSession")

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
                    return_value="arn:aws:bedrock-agentcore:us-east-1:123:runtime/rt-test",
                ),
                patch.dict("sys.modules", {"boto3": mock_boto3}),
                patch("container.code_mcp_server.boto3", mock_boto3, create=True),
            ):
                result = await cancel_task(job_id=job_id, _user_id=user_id)

            # task.cancel() must have been attempted FIRST
            assert call_order[0] == "task.cancel", (
                f"Expected task.cancel to be attempted first, got: {call_order}"
            )
            # StopRuntimeSession must have been called as fallback AFTER
            assert "StopRuntimeSession" in call_order, (
                f"Expected StopRuntimeSession fallback after in-process failure, got: {call_order}"
            )
            assert call_order.index("task.cancel") < call_order.index("StopRuntimeSession"), (
                f"task.cancel must come before StopRuntimeSession, got: {call_order}"
            )
            assert result["status"] == "CANCELLED"

        finally:
            _running_tasks.pop(job_id, None)
            _cancel_flags.pop(job_id, None)
