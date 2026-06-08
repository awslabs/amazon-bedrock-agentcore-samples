# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property tests for the MCP server tools (code_mcp_server.py).

Properties 3, 4, 6-14, 16 from the design document. Properties 1, 2, 5,
and 15 (which exercise the 5-step pipeline body end-to-end) now live in
``tests/property/test_pipeline_properties.py`` because the pipeline body
moved out of ``code_mcp_server`` and into ``container.pipeline``.

Each test uses Hypothesis @given with @settings(max_examples=100).

External dependencies (fastmcp, bedrock_agentcore, strands) are stubbed
before importing the module under test.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Stub external dependencies before importing the module under test.
# The root conftest.py already sets up the stubs; we just ensure they
# are present for clarity.
# ---------------------------------------------------------------------------
fastmcp_mock = MagicMock()
# Make @mcp.tool() a pass-through decorator so the real async functions
# are importable and callable.
fastmcp_mock.FastMCP.return_value.tool.return_value = lambda fn: fn
sys.modules["fastmcp"] = fastmcp_mock

agentcore_mock = MagicMock()
agentcore_mock.BedrockAgentCoreApp.return_value = MagicMock()
sys.modules["bedrock_agentcore"] = agentcore_mock
sys.modules["bedrock_agentcore.runtime"] = agentcore_mock

strands_mock = MagicMock()
strands_mock.tool = lambda fn: fn
sys.modules["strands"] = strands_mock

# Now safe to import
from container.code_mcp_server import (
    code,
    run_coding_task,
    _running_tasks,
    _cancel_flags,
    app,
    mcp,
)
from container.code_mcp_server import (
    cancel_task,
)
from container.lib.dynamodb_helpers import (
    write_job_record,
    update_job_status,
    query_job_record,
    query_user_jobs,
    VALID_STATES,
)


# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------
user_id_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=40,
)
job_id_st = st.uuids().map(str)
repo_url_st = st.just("https://github.com/owner/repo")
branch_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_/"),
    min_size=1,
    max_size=30,
)
task_desc_st = st.text(min_size=1, max_size=200)


# ===========================================================================
# 3.3 — Property 3: Timeout validation rejects out-of-range values
# Validates: Requirements 2.7
# ===========================================================================
class TestTimeoutValidation:
    """For any integer outside [1, 30], verify the code tool returns a
    validation error.
    """

    @given(
        timeout=st.integers().filter(lambda t: t < 1 or t > 30),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_out_of_range_timeout_rejected(self, timeout):
        """**Validates: Requirements 2.7**"""
        result = await code(
            task_description="task",
            repo_url="https://github.com/o/r",
            base_branch="main",
            timeout_minutes=timeout,
            _user_id="user1",
            ctx=MagicMock(),
        )

        assert result["status"] == "failed"
        assert "timeout_minutes" in result["error"].lower() or "timeout" in result["error"].lower()


# ===========================================================================
# 3.4 — Property 4: Async task immediate return schema
# Validates: Requirements 4.3
# ===========================================================================
class TestAsyncTaskImmediateReturn:
    """For any valid run_coding_task input, verify return contains job_id
    (UUID) and status='RUNNING'.
    """

    @given(
        user_id=user_id_st,
        task_desc=task_desc_st,
        base_branch=branch_st,
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_immediate_return_schema(self, user_id, task_desc, base_branch):
        """**Validates: Requirements 4.3**"""
        with (
            patch("container.code_mcp_server.app") as mock_app,
            patch("container.code_mcp_server.run_coding_pipeline", new_callable=AsyncMock),
        ):
            result = await run_coding_task(
                task_description=task_desc,
                repo_url="https://github.com/o/r",
                base_branch=base_branch,
                _user_id=user_id,
                ctx=None,
            )

        assert result["status"] == "RUNNING"
        # job_id must be a valid UUID
        parsed = uuid.UUID(result["job_id"])
        assert str(parsed) == result["job_id"]

        # Clean up any spawned tasks
        job_id = result["job_id"]
        task = _running_tasks.pop(job_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        _cancel_flags.pop(job_id, None)


# ===========================================================================
# 3.6 — Property 6: Job state validity
# Validates: Requirements 8.1
# ===========================================================================
class TestJobStateValidity:
    """For any sequence of job operations, verify all status values are in
    {RUNNING, COMPLETE, FAILED, CANCELLED}.
    """

    @given(
        statuses=st.lists(
            st.sampled_from(["RUNNING", "COMPLETE", "FAILED", "CANCELLED"]),
            min_size=1,
            max_size=10,
        ),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_all_states_valid(self, statuses):
        """**Validates: Requirements 8.1**"""
        mock_table = MagicMock()
        mock_table.put_item = MagicMock()

        written_items = []
        original_put = mock_table.put_item

        def capture_put(Item):
            written_items.append(Item)

        mock_table.put_item = capture_put

        with patch("container.lib.dynamodb_helpers._get_ddb") as mock_ddb:
            mock_ddb.return_value.Table.return_value = mock_table

            for status in statuses:
                await write_job_record(
                    job_id=str(uuid.uuid4()),
                    user_id="user1",
                    status=status,
                    task_description="test",
                )

        for item in written_items:
            assert item["status"] in VALID_STATES


# ===========================================================================
# 3.7 — Property 7: DynamoDB key format and record schema
# Validates: Requirements 8.3, 8.4
# ===========================================================================
class TestDynamoDBKeyFormatAndSchema:
    """For any user_id and job_id, verify PK matches user#{user_id},
    SK matches job#{job_id}#{iso}, and all required attributes present
    including runtime_session_id.
    """

    @given(
        user_id=user_id_st,
        job_id=job_id_st,
        session_id=st.text(min_size=0, max_size=50),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_key_format_and_attributes(self, user_id, job_id, session_id):
        """**Validates: Requirements 8.3, 8.4**"""
        captured_items = []
        mock_table = MagicMock()
        mock_table.put_item = lambda Item: captured_items.append(Item)

        with patch("container.lib.dynamodb_helpers._get_ddb") as mock_ddb:
            mock_ddb.return_value.Table.return_value = mock_table

            await write_job_record(
                job_id=job_id,
                user_id=user_id,
                status="RUNNING",
                task_description="test",
                repo_url="https://github.com/o/r",
                base_branch="main",
                target_branch="feature",
                runtime_session_id=session_id,
            )

        assert len(captured_items) == 1
        item = captured_items[0]

        # PK format
        assert item["PK"] == f"user#{user_id}"
        # SK format: job#{job_id}#{iso_timestamp}
        assert item["SK"].startswith(f"job#{job_id}#")
        sk_parts = item["SK"].split("#", 2)
        assert len(sk_parts) == 3
        # Third part should be an ISO timestamp — just verify it's non-empty
        assert len(sk_parts[2]) > 0

        # Required attributes
        required_attrs = [
            "job_id", "user_id", "status", "task_description",
            "repo_url", "base_branch", "target_branch",
            "runtime_session_id", "created_at",
        ]
        for attr in required_attrs:
            assert attr in item, f"Missing required attribute: {attr}"

        assert item["runtime_session_id"] == session_id


# ===========================================================================
# 3.8 — Property 10: list_tasks user scoping
# Validates: Requirements 6.2
# ===========================================================================
class TestListTasksUserScoping:
    """For any list_tasks call with a given user_id, verify the DynamoDB
    query uses partition key PK = user#{user_id}.
    """

    @given(user_id=user_id_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_user_scoped_query(self, user_id):
        """**Validates: Requirements 6.2**"""
        captured_kwargs = []
        mock_table = MagicMock()

        def capture_query(**kwargs):
            captured_kwargs.append(kwargs)
            return {"Items": []}

        mock_table.query = capture_query

        with patch("container.lib.dynamodb_helpers._get_ddb") as mock_ddb:
            mock_ddb.return_value.Table.return_value = mock_table

            await query_user_jobs(user_id=user_id)

        assert len(captured_kwargs) == 1
        expr_values = captured_kwargs[0]["ExpressionAttributeValues"]
        assert expr_values[":pk"] == f"user#{user_id}"


# ===========================================================================
# 3.9 — Property 11: list_tasks status filtering
# Validates: Requirements 6.3
# ===========================================================================
class TestListTasksStatusFiltering:
    """For any set of jobs with mixed statuses and any filter, verify only
    matching jobs returned.
    """

    @given(
        filter_status=st.sampled_from(["RUNNING", "COMPLETE", "FAILED", "CANCELLED"]),
        job_statuses=st.lists(
            st.sampled_from(["RUNNING", "COMPLETE", "FAILED", "CANCELLED"]),
            min_size=1,
            max_size=20,
        ),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_status_filter(self, filter_status, job_statuses):
        """**Validates: Requirements 6.3**"""
        # Build fake DynamoDB items
        all_items = []
        for i, status in enumerate(job_statuses):
            all_items.append({
                "PK": "user#testuser",
                "SK": f"job#{uuid.uuid4()}#2025-01-01T00:00:00+00:00",
                "job_id": str(uuid.uuid4()),
                "status": status,
            })

        mock_table = MagicMock()

        def mock_query(**kwargs):
            # Simulate DynamoDB FilterExpression behavior
            filter_expr = kwargs.get("FilterExpression", "")
            if filter_expr:
                sf = kwargs["ExpressionAttributeValues"].get(":sf", "")
                filtered = [item for item in all_items if item["status"] == sf]
            else:
                filtered = all_items
            limited = filtered[: kwargs.get("Limit", 50)]
            return {"Items": limited}

        mock_table.query = mock_query

        with patch("container.lib.dynamodb_helpers._get_ddb") as mock_ddb:
            mock_ddb.return_value.Table.return_value = mock_table

            result = await query_user_jobs(
                user_id="testuser",
                status_filter=filter_status,
            )

        for job in result["jobs"]:
            assert job["status"] == filter_status


# ===========================================================================
# 3.10 — Property 12: list_tasks limit capping
# Validates: Requirements 6.4
# ===========================================================================
class TestListTasksLimitCapping:
    """For any limit > 100, verify effective limit is 100."""

    @given(limit=st.integers(min_value=101, max_value=10_000))
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_limit_capped_at_100(self, limit):
        """**Validates: Requirements 6.4**"""
        captured_kwargs = []
        mock_table = MagicMock()

        def capture_query(**kwargs):
            captured_kwargs.append(kwargs)
            return {"Items": []}

        mock_table.query = capture_query

        with patch("container.lib.dynamodb_helpers._get_ddb") as mock_ddb:
            mock_ddb.return_value.Table.return_value = mock_table

            await query_user_jobs(user_id="testuser", limit=limit)

        assert len(captured_kwargs) == 1
        assert captured_kwargs[0]["Limit"] <= 100


# ===========================================================================
# 3.11 — Property 13: Cancel rejects terminal state jobs
# Validates: Requirements 7.3
# ===========================================================================
class TestCancelRejectsTerminalState:
    """For any job in terminal state (COMPLETE, FAILED, CANCELLED), verify
    cancel_task returns error without modifying the record.
    """

    @given(
        terminal_status=st.sampled_from(["COMPLETE", "FAILED", "CANCELLED"]),
        user_id=user_id_st,
        job_id=job_id_st,
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_terminal_state_rejected(self, terminal_status, user_id, job_id):
        """**Validates: Requirements 7.3**"""
        update_calls = []

        async def mock_query(job_id, user_id):
            return {
                "job_id": job_id,
                "status": terminal_status,
                "user_id": user_id,
            }

        async def mock_update(*args, **kwargs):
            update_calls.append(kwargs)

        with (
            patch("container.code_mcp_server.query_job_record", side_effect=mock_query),
            patch("container.code_mcp_server.update_job_status", side_effect=mock_update),
        ):
            result = await cancel_task(job_id=job_id, _user_id=user_id)

        assert "error" in result
        assert "terminal" in result["error"].lower()
        # Record must NOT be modified
        assert len(update_calls) == 0


# ===========================================================================
# 3.12 — Property 14: Cancellation user ownership
# Validates: Requirements 20.1
# ===========================================================================
class TestCancellationUserOwnership:
    """For any two distinct user_ids, verify user A cannot cancel user B's job."""

    @given(
        user_a=user_id_st,
        user_b=user_id_st,
        job_id=job_id_st,
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_user_cannot_cancel_others_job(self, user_a, user_b, job_id):
        """**Validates: Requirements 20.1**"""
        assume(user_a != user_b)

        async def mock_query(job_id, user_id):
            # Job belongs to user_b; query scoped to user_a returns None
            if user_id == user_b:
                return {"job_id": job_id, "status": "RUNNING", "user_id": user_b}
            return None  # user_a can't see user_b's job

        with patch("container.code_mcp_server.query_job_record", side_effect=mock_query):
            result = await cancel_task(job_id=job_id, _user_id=user_a)

        assert "error" in result
        assert "not found" in result["error"].lower()


# ===========================================================================
# 3.14 — Property 16: HealthyBusy while tasks active
# Validates: Requirements 15.1, 15.2
# ===========================================================================
class TestHealthyBusyWhileTasksActive:
    """For any number of concurrent background async tasks > 0, verify
    ``app.add_async_task`` and ``app.complete_async_task`` are both called
    for every spawned task.

    Exercises ``run_coding_task`` directly with ``run_coding_pipeline``
    mocked out. ``add_async_task`` is called inline before the background
    coroutine is scheduled; ``complete_async_task`` is called from the
    ``finally`` block of the inline ``_background()`` coroutine, so the
    test awaits each spawned ``asyncio.Task`` (grabbed from
    ``_running_tasks[job_id]``) to let the ``finally`` run.
    """

    @given(
        num_tasks=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_healthy_busy_signaling(self, num_tasks):
        """**Validates: Requirements 15.1, 15.2**"""
        mock_app = MagicMock()
        add_calls: list[str] = []
        complete_calls: list[str] = []

        mock_app.add_async_task = lambda jid: add_calls.append(jid)
        mock_app.complete_async_task = lambda jid: complete_calls.append(jid)

        with (
            patch("container.code_mcp_server.run_coding_pipeline", new_callable=AsyncMock),
            patch("container.code_mcp_server.app", mock_app),
        ):
            spawned_job_ids: list[str] = []
            for _ in range(num_tasks):
                result = await run_coding_task(
                    task_description="task",
                    repo_url="https://github.com/o/r",
                    base_branch="main",
                    target_branch="feature",
                    _user_id="user1",
                    ctx=None,
                )
                assert result["status"] == "RUNNING"
                spawned_job_ids.append(result["job_id"])

            # Let every spawned background task run its finally block so
            # ``complete_async_task`` is invoked and ``_running_tasks`` /
            # ``_cancel_flags`` are cleaned up.
            for jid in spawned_job_ids:
                task = _running_tasks.get(jid)
                if task is not None:
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):
                        pass

        # add_async_task was called for every spawned task.
        assert len(add_calls) == num_tasks
        assert set(add_calls) == set(spawned_job_ids)

        # complete_async_task was called for every spawned task.
        assert len(complete_calls) == num_tasks
        assert set(complete_calls) == set(spawned_job_ids)

        # After completion, no jobs remain in the in-process registry.
        for jid in spawned_job_ids:
            assert jid not in _running_tasks
            assert jid not in _cancel_flags
