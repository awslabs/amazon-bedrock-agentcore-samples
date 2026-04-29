# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property test: cancel_task always updates DynamoDB to CANCELLED.

Feature: 13-runtime-consolidation
Property 1: Cancel task always updates DynamoDB to CANCELLED

For any running job and any combination of cancellation outcomes
(in-process success, in-process failure with cross-session success,
in-process failure with cross-session failure, job not in _running_tasks),
calling cancel_task SHALL update the DynamoDB record status to CANCELLED.

Validates: Requirements 6.3
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# The root conftest.py stubs fastmcp, bedrock_agentcore, and strands.
# Import the unified cancel_task from the consolidated server.
# ---------------------------------------------------------------------------
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
session_id_st = st.text(min_size=0, max_size=50)


# A strategy for the different cancellation scenarios
cancel_scenario_st = st.sampled_from([
    "in_process_success",
    "in_process_failure_cross_session_success",
    "in_process_failure_cross_session_failure",
    "not_in_running_tasks_cross_session_success",
    "not_in_running_tasks_cross_session_failure",
])


class TestCancelTaskAlwaysUpdatesDynamoDB:
    """**Feature: 13-runtime-consolidation, Property 1: Cancel task always updates DynamoDB to CANCELLED**"""

    @given(
        job_id=job_id_st,
        user_id=user_id_st,
        session_id=session_id_st,
        scenario=cancel_scenario_st,
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_cancel_always_updates_dynamodb_to_cancelled(
        self, job_id, user_id, session_id, scenario
    ):
        """**Validates: Requirements 6.3**

        Regardless of whether in-process cancellation succeeds, fails,
        or the job isn't in _running_tasks at all, and regardless of
        whether StopRuntimeSession succeeds or fails, update_job_status
        must always be called with status="CANCELLED".
        """
        # Track update_job_status calls
        update_calls = []

        async def mock_query_job_record(job_id, user_id):
            return {
                "job_id": job_id,
                "status": "RUNNING",
                "user_id": user_id,
                "runtime_session_id": session_id,
            }

        async def mock_update_job_status(job_id, user_id, status, **kwargs):
            update_calls.append({"job_id": job_id, "user_id": user_id, "status": status})

        # Set up _running_tasks based on scenario
        in_running = scenario.startswith("in_process")
        mock_task = MagicMock()

        if in_running:
            if scenario == "in_process_success":
                mock_task.cancel = MagicMock()  # cancel() succeeds
            else:
                # in_process_failure — cancel() raises
                mock_task.cancel = MagicMock(side_effect=Exception("task already done"))
            _running_tasks[job_id] = mock_task
            _cancel_flags[job_id] = False

        # Set up StopRuntimeSession mock
        cross_session_succeeds = scenario in (
            "in_process_success",  # won't be called, but mock anyway
            "in_process_failure_cross_session_success",
            "not_in_running_tasks_cross_session_success",
        )

        mock_boto_client = MagicMock()
        if cross_session_succeeds:
            mock_boto_client.stop_runtime_session = MagicMock()
        else:
            mock_boto_client.stop_runtime_session = MagicMock(
                side_effect=Exception("StopRuntimeSession failed")
            )

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

            # The key property: update_job_status is ALWAYS called with CANCELLED
            assert len(update_calls) == 1, (
                f"Expected exactly 1 update_job_status call, got {len(update_calls)}"
            )
            assert update_calls[0]["status"] == "CANCELLED", (
                f"Expected status='CANCELLED', got '{update_calls[0]['status']}'"
            )
            assert update_calls[0]["job_id"] == job_id
            assert update_calls[0]["user_id"] == user_id

            # Result should confirm cancellation
            assert result["status"] == "CANCELLED"
            assert result["job_id"] == job_id

        finally:
            # Clean up module-level dicts to avoid cross-test pollution
            _running_tasks.pop(job_id, None)
            _cancel_flags.pop(job_id, None)
