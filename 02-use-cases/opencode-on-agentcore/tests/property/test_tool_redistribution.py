# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property tests for tool redistribution (spec 11-tool-redistribution-cold-start).

Each test uses Hypothesis @given with @settings(max_examples=100).

External dependencies (fastmcp, bedrock_agentcore, strands) are stubbed
by the root conftest.py before importing the module under test.
"""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Ensure stubs are present (root conftest.py sets these up)
# ---------------------------------------------------------------------------
fastmcp_mock = MagicMock()
fastmcp_mock.FastMCP.return_value.tool.return_value = lambda fn: fn
sys.modules.setdefault("fastmcp", fastmcp_mock)

# Now safe to import — unified server after runtime consolidation (spec 13)
from container.code_mcp_server import cancel_task, get_task_status, list_tasks


# ---------------------------------------------------------------------------
# Shared strategies
# ---------------------------------------------------------------------------
user_id_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=40,
)
job_id_st = st.uuids().map(str)

# Strategy for a complete job record as returned by DynamoDB
job_record_st = st.fixed_dictionaries({
    "job_id": job_id_st,
    "user_id": user_id_st,
    "status": st.sampled_from(["RUNNING", "COMPLETE", "FAILED", "CANCELLED"]),
    "task_description": st.text(min_size=0, max_size=200),
    "repo_url": st.text(min_size=0, max_size=200),
    "base_branch": st.text(min_size=0, max_size=50),
    "target_branch": st.text(min_size=0, max_size=50),
    "pr_url": st.text(min_size=0, max_size=200),
    "stop_reason": st.text(min_size=0, max_size=100),
    "files_edited": st.lists(st.text(min_size=1, max_size=50), max_size=10),
    "duration_seconds": st.integers(min_value=0, max_value=3600),
    "error": st.text(min_size=0, max_size=500),
    "created_at": st.text(min_size=0, max_size=30),
    "completed_at": st.text(min_size=0, max_size=30),
})


# ===========================================================================
# Feature: 11-tool-redistribution-cold-start, Property 1: get_task_status equivalence
# Validates: Requirements 1.1, 2.1, 2.4, 4.3
# ===========================================================================
class TestGetTaskStatusEquivalence:
    """For any valid job record, get_task_status(job_id, user_id) returns
    the expected response dict shape.
    """

    # Expected response keys from the original implementation
    EXPECTED_KEYS = {
        "job_id", "status", "task_description", "repo_url",
        "base_branch", "target_branch", "pr_url", "stop_reason",
        "files_edited", "duration_seconds", "error",
        "created_at", "completed_at",
    }

    @given(
        job_id=job_id_st,
        user_id=user_id_st,
        record=job_record_st,
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_response_matches_original_schema(self, job_id, user_id, record):
        """**Validates: Requirements 1.1, 2.1, 2.4, 4.3**

        For any valid job record returned by query_job_record, the response
        from get_task_status must contain exactly the expected keys with
        values matching the record fields (using .get() defaults).
        """
        async def mock_query(job_id, user_id):
            return record

        with patch(
            "container.code_mcp_server.query_job_record",
            side_effect=mock_query,
        ):
            result = await get_task_status(job_id=job_id, _user_id=user_id)

        # Response must have exactly the expected keys
        assert set(result.keys()) == self.EXPECTED_KEYS

        # Each field must match the record value via .get() with defaults
        assert result["job_id"] == record.get("job_id", "")
        assert result["status"] == record.get("status", "")
        assert result["task_description"] == record.get("task_description", "")
        assert result["repo_url"] == record.get("repo_url", "")
        assert result["base_branch"] == record.get("base_branch", "")
        assert result["target_branch"] == record.get("target_branch", "")
        assert result["pr_url"] == record.get("pr_url", "")
        assert result["stop_reason"] == record.get("stop_reason", "")
        assert result["files_edited"] == record.get("files_edited", [])
        assert result["duration_seconds"] == record.get("duration_seconds", 0)
        assert result["error"] == record.get("error", "")
        assert result["created_at"] == record.get("created_at", "")
        assert result["completed_at"] == record.get("completed_at", "")

    @given(
        job_id=job_id_st,
        user_id=user_id_st,
        record=job_record_st,
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_response_types_match_original(self, job_id, user_id, record):
        """**Validates: Requirements 1.1, 2.1, 2.4, 4.3**

        For any valid job record, the response field types must match
        the original implementation's types.
        """
        async def mock_query(job_id, user_id):
            return record

        with patch(
            "container.code_mcp_server.query_job_record",
            side_effect=mock_query,
        ):
            result = await get_task_status(job_id=job_id, _user_id=user_id)

        # Type checks matching the original implementation
        assert isinstance(result["job_id"], str)
        assert isinstance(result["status"], str)
        assert isinstance(result["task_description"], str)
        assert isinstance(result["repo_url"], str)
        assert isinstance(result["base_branch"], str)
        assert isinstance(result["target_branch"], str)
        assert isinstance(result["pr_url"], str)
        assert isinstance(result["stop_reason"], str)
        assert isinstance(result["files_edited"], list)
        assert isinstance(result["duration_seconds"], (int, float))
        assert isinstance(result["error"], str)
        assert isinstance(result["created_at"], str)
        assert isinstance(result["completed_at"], str)

    @given(job_id=job_id_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_empty_user_id_returns_error(self, job_id):
        """**Validates: Requirements 1.1, 2.1, 2.4, 4.3**

        When _user_id is empty, get_task_status returns an error dict.
        """
        result = await get_task_status(job_id=job_id, _user_id="")

        assert "error" in result
        assert "user_id" in result["error"].lower()

    @given(job_id=job_id_st, user_id=user_id_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_nonexistent_job_returns_error(self, job_id, user_id):
        """**Validates: Requirements 1.1, 2.1, 2.4, 4.3**

        When query_job_record returns None, get_task_status returns an error.
        """
        async def mock_query(job_id, user_id):
            return None

        with patch(
            "container.code_mcp_server.query_job_record",
            side_effect=mock_query,
        ):
            result = await get_task_status(job_id=job_id, _user_id=user_id)

        assert "error" in result
        assert "not found" in result["error"].lower()


# ===========================================================================
# Feature: 11-tool-redistribution-cold-start, Property 2: list_tasks user scoping and schema
# Validates: Requirements 1.2, 2.2
# ===========================================================================
class TestListTasksUserScopingAndSchema:
    """For any set of job records belonging to multiple users,
    list_tasks(status, limit, user_id) returns only jobs belonging to the
    specified user, with correct response schema and count not exceeding
    min(limit, 100).
    """

    @given(
        target_user=user_id_st,
        other_users=st.lists(user_id_st, min_size=1, max_size=5),
        target_jobs=st.lists(job_record_st, min_size=0, max_size=10),
        other_jobs=st.lists(job_record_st, min_size=0, max_size=10),
        status_filter=st.sampled_from(["", "RUNNING", "COMPLETE", "FAILED", "CANCELLED"]),
        limit=st.integers(min_value=1, max_value=200),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_returns_only_target_user_jobs_with_correct_schema(
        self, target_user, other_users, target_jobs, other_jobs, status_filter, limit,
    ):
        """**Validates: Requirements 1.2, 2.2**

        For any mix of job records across multiple users, list_tasks returns
        only the target user's jobs with correct schema and capped count.
        """
        # Stamp target_user onto target_jobs
        for job in target_jobs:
            job["user_id"] = target_user

        # Apply status filter to simulate what DynamoDB would return
        if status_filter:
            filtered = [j for j in target_jobs if j["status"] == status_filter]
        else:
            filtered = list(target_jobs)

        effective_limit = min(limit, 100)
        returned_jobs = filtered[:effective_limit]

        async def mock_query_user_jobs(user_id, status_filter="", limit=50):
            # Simulate DynamoDB: only return jobs for the queried user
            assert user_id == target_user
            return {"jobs": returned_jobs, "count": len(returned_jobs)}

        with patch(
            "container.code_mcp_server.query_user_jobs",
            side_effect=mock_query_user_jobs,
        ):
            result = await list_tasks(
                status=status_filter, limit=limit, _user_id=target_user,
            )

        # Schema: must have "jobs" (list) and "count" (int)
        assert "jobs" in result
        assert "count" in result
        assert isinstance(result["jobs"], list)
        assert isinstance(result["count"], int)

        # All returned jobs belong to the target user
        for job in result["jobs"]:
            assert job["user_id"] == target_user

        # Count must not exceed min(limit, 100)
        assert result["count"] <= effective_limit

    @given(
        user_id=user_id_st,
        limit=st.integers(min_value=1, max_value=200),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_limit_capped_at_100(self, user_id, limit):
        """**Validates: Requirements 1.2, 2.2**

        list_tasks passes min(limit, 100) to query_user_jobs, ensuring
        the count never exceeds 100 regardless of the requested limit.
        """
        effective_limit = min(limit, 100)
        captured_limits = []

        async def mock_query_user_jobs(user_id, status_filter="", limit=50):
            captured_limits.append(limit)
            return {"jobs": [], "count": 0}

        with patch(
            "container.code_mcp_server.query_user_jobs",
            side_effect=mock_query_user_jobs,
        ):
            await list_tasks(status="", limit=limit, _user_id=user_id)

        assert len(captured_limits) == 1
        assert captured_limits[0] == effective_limit

    @given(
        status_filter=st.sampled_from(["", "RUNNING", "COMPLETE", "FAILED", "CANCELLED"]),
        limit=st.integers(min_value=1, max_value=200),
    )
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_empty_user_id_returns_error(self, status_filter, limit):
        """**Validates: Requirements 1.2, 2.2**

        When _user_id is empty, list_tasks returns an error dict without
        querying DynamoDB.
        """
        result = await list_tasks(status=status_filter, limit=limit, _user_id="")

        assert "error" in result
        assert "user_id" in result["error"].lower()


# ===========================================================================
# Feature: 11-tool-redistribution-cold-start, Property 3: cancel_task cross-session cancellation
# Validates: Requirements 1.3, 2.3, 3.1
# ===========================================================================
class TestCancelTaskCrossSession:
    """For any RUNNING job with a valid runtime_session_id, cancel_task
    calls StopRuntimeSession with the correct ARN and session ID, updates
    DynamoDB to CANCELLED, and returns correct response.
    """

    # Strategy for a RUNNING job record with a session ID
    running_job_st = st.fixed_dictionaries({
        "job_id": job_id_st,
        "user_id": user_id_st,
        "status": st.just("RUNNING"),
        "task_description": st.text(min_size=0, max_size=200),
        "repo_url": st.text(min_size=0, max_size=200),
        "base_branch": st.text(min_size=0, max_size=50),
        "target_branch": st.text(min_size=0, max_size=50),
        "pr_url": st.text(min_size=0, max_size=200),
        "stop_reason": st.text(min_size=0, max_size=100),
        "files_edited": st.lists(st.text(min_size=1, max_size=50), max_size=10),
        "duration_seconds": st.integers(min_value=0, max_value=3600),
        "error": st.text(min_size=0, max_size=500),
        "created_at": st.text(min_size=0, max_size=30),
        "completed_at": st.text(min_size=0, max_size=30),
        "runtime_session_id": st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
            min_size=1,
            max_size=60,
        ),
    })

    FAKE_RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test-runtime-id"

    @given(record=running_job_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_stop_runtime_session_called_with_correct_args(self, record):
        """**Validates: Requirements 1.3, 2.3, 3.1**

        For any RUNNING job with a session_id, cancel_task calls
        StopRuntimeSession with the correct runtime ARN and session ID.
        """
        job_id = record["job_id"]
        user_id = record["user_id"]
        session_id = record["runtime_session_id"]

        async def mock_query(job_id, user_id):
            return record

        mock_client = MagicMock()
        mock_client.stop_runtime_session = MagicMock()

        async def mock_update(job_id, user_id, status, **kwargs):
            pass

        with patch(
            "container.code_mcp_server.query_job_record",
            side_effect=mock_query,
        ), patch(
            "container.code_mcp_server.update_job_status",
            side_effect=mock_update,
        ), patch(
            "boto3.client",
            return_value=mock_client,
        ), patch(
            "container.code_mcp_server._get_runtime_arn",
            return_value=self.FAKE_RUNTIME_ARN,
        ):
            result = await cancel_task(job_id=job_id, _user_id=user_id)

        # StopRuntimeSession must be called with correct ARN and session ID
        mock_client.stop_runtime_session.assert_called_once_with(
            agentRuntimeArn=self.FAKE_RUNTIME_ARN,
            runtimeSessionId=session_id,
        )

    @given(record=running_job_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_dynamodb_updated_to_cancelled(self, record):
        """**Validates: Requirements 1.3, 2.3, 3.1**

        For any RUNNING job, cancel_task updates DynamoDB status to CANCELLED.
        """
        job_id = record["job_id"]
        user_id = record["user_id"]

        async def mock_query(job_id, user_id):
            return record

        captured_updates = []

        async def mock_update(job_id, user_id, status, **kwargs):
            captured_updates.append({"job_id": job_id, "user_id": user_id, "status": status})

        mock_client = MagicMock()

        with patch(
            "container.code_mcp_server.query_job_record",
            side_effect=mock_query,
        ), patch(
            "container.code_mcp_server.update_job_status",
            side_effect=mock_update,
        ), patch(
            "boto3.client",
            return_value=mock_client,
        ), patch(
            "container.code_mcp_server._get_runtime_arn",
            return_value=self.FAKE_RUNTIME_ARN,
        ):
            await cancel_task(job_id=job_id, _user_id=user_id)

        # update_job_status must be called with status="CANCELLED"
        assert len(captured_updates) == 1
        assert captured_updates[0]["job_id"] == job_id
        assert captured_updates[0]["user_id"] == user_id
        assert captured_updates[0]["status"] == "CANCELLED"

    @given(record=running_job_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_returns_job_id_and_cancelled_status(self, record):
        """**Validates: Requirements 1.3, 2.3, 3.1**

        For any RUNNING job, cancel_task returns a response containing
        the job_id and status "CANCELLED".
        """
        job_id = record["job_id"]
        user_id = record["user_id"]

        async def mock_query(job_id, user_id):
            return record

        async def mock_update(job_id, user_id, status, **kwargs):
            pass

        mock_client = MagicMock()

        with patch(
            "container.code_mcp_server.query_job_record",
            side_effect=mock_query,
        ), patch(
            "container.code_mcp_server.update_job_status",
            side_effect=mock_update,
        ), patch(
            "boto3.client",
            return_value=mock_client,
        ), patch(
            "container.code_mcp_server._get_runtime_arn",
            return_value=self.FAKE_RUNTIME_ARN,
        ):
            result = await cancel_task(job_id=job_id, _user_id=user_id)

        # Response must contain job_id and status CANCELLED
        assert result["job_id"] == job_id
        assert result["status"] == "CANCELLED"


# ===========================================================================
# Feature: 11-tool-redistribution-cold-start, Property 4: cancel_task rejects terminal states
# Validates: Requirements 3.3
# ===========================================================================
class TestCancelTaskTerminalStateRejection:
    """For any job in COMPLETE, FAILED, or CANCELLED state, cancel_task
    returns an error without calling StopRuntimeSession or modifying DynamoDB.
    """

    # Strategy for a terminal-state job record
    terminal_job_st = st.fixed_dictionaries({
        "job_id": job_id_st,
        "user_id": user_id_st,
        "status": st.sampled_from(["COMPLETE", "FAILED", "CANCELLED"]),
        "task_description": st.text(min_size=0, max_size=200),
        "repo_url": st.text(min_size=0, max_size=200),
        "base_branch": st.text(min_size=0, max_size=50),
        "target_branch": st.text(min_size=0, max_size=50),
        "pr_url": st.text(min_size=0, max_size=200),
        "stop_reason": st.text(min_size=0, max_size=100),
        "files_edited": st.lists(st.text(min_size=1, max_size=50), max_size=10),
        "duration_seconds": st.integers(min_value=0, max_value=3600),
        "error": st.text(min_size=0, max_size=500),
        "created_at": st.text(min_size=0, max_size=30),
        "completed_at": st.text(min_size=0, max_size=30),
        "runtime_session_id": st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
            min_size=0,
            max_size=60,
        ),
    })

    FAKE_RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test-runtime-id"

    @given(record=terminal_job_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_returns_error_with_terminal_message(self, record):
        """**Validates: Requirements 3.3**

        For any job in a terminal state, cancel_task returns a response
        containing "error" with "terminal" in the message.
        """
        job_id = record["job_id"]
        user_id = record["user_id"]

        async def mock_query(job_id, user_id):
            return record

        with patch(
            "container.code_mcp_server.query_job_record",
            side_effect=mock_query,
        ):
            result = await cancel_task(job_id=job_id, _user_id=user_id)

        assert "error" in result
        assert "terminal" in result["error"].lower()

    @given(record=terminal_job_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_stop_runtime_session_not_called(self, record):
        """**Validates: Requirements 3.3**

        For any job in a terminal state, cancel_task does NOT call
        StopRuntimeSession.
        """
        job_id = record["job_id"]
        user_id = record["user_id"]

        async def mock_query(job_id, user_id):
            return record

        mock_client = MagicMock()
        mock_client.stop_runtime_session = MagicMock()

        with patch(
            "container.code_mcp_server.query_job_record",
            side_effect=mock_query,
        ), patch(
            "boto3.client",
            return_value=mock_client,
        ), patch(
            "container.code_mcp_server._get_runtime_arn",
            return_value=self.FAKE_RUNTIME_ARN,
        ):
            await cancel_task(job_id=job_id, _user_id=user_id)

        mock_client.stop_runtime_session.assert_not_called()

    @given(record=terminal_job_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_update_job_status_not_called(self, record):
        """**Validates: Requirements 3.3**

        For any job in a terminal state, cancel_task does NOT call
        update_job_status (DynamoDB is not modified).
        """
        job_id = record["job_id"]
        user_id = record["user_id"]

        async def mock_query(job_id, user_id):
            return record

        mock_update = AsyncMock()

        with patch(
            "container.code_mcp_server.query_job_record",
            side_effect=mock_query,
        ), patch(
            "container.code_mcp_server.update_job_status",
            mock_update,
        ):
            await cancel_task(job_id=job_id, _user_id=user_id)

        mock_update.assert_not_called()


# ===========================================================================
# Feature: 11-tool-redistribution-cold-start, Property 5: cancel_task resilient to StopRuntimeSession failures
# Validates: Requirements 3.4
# ===========================================================================
class TestCancelTaskStopRuntimeSessionResilience:
    """For any RUNNING job, when StopRuntimeSession raises an exception,
    cancel_task still updates DynamoDB to CANCELLED and returns success.
    """

    # Strategy for a RUNNING job record with a session ID
    running_job_st = st.fixed_dictionaries({
        "job_id": job_id_st,
        "user_id": user_id_st,
        "status": st.just("RUNNING"),
        "task_description": st.text(min_size=0, max_size=200),
        "repo_url": st.text(min_size=0, max_size=200),
        "base_branch": st.text(min_size=0, max_size=50),
        "target_branch": st.text(min_size=0, max_size=50),
        "pr_url": st.text(min_size=0, max_size=200),
        "stop_reason": st.text(min_size=0, max_size=100),
        "files_edited": st.lists(st.text(min_size=1, max_size=50), max_size=10),
        "duration_seconds": st.integers(min_value=0, max_value=3600),
        "error": st.text(min_size=0, max_size=500),
        "created_at": st.text(min_size=0, max_size=30),
        "completed_at": st.text(min_size=0, max_size=30),
        "runtime_session_id": st.text(
            alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
            min_size=1,
            max_size=60,
        ),
    })

    # Strategy for various exception types that StopRuntimeSession might raise
    exception_st = st.sampled_from([
        ConnectionError("Connection refused"),
        TimeoutError("Request timed out"),
        RuntimeError("Internal server error"),
        ValueError("Invalid parameter"),
        OSError("Network unreachable"),
        Exception("Unknown error"),
        PermissionError("Access denied"),
        BrokenPipeError("Broken pipe"),
    ])

    FAKE_RUNTIME_ARN = "arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/test-runtime-id"

    @given(record=running_job_st, exc=exception_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_returns_success_despite_stop_session_failure(self, record, exc):
        """**Validates: Requirements 3.4**

        For any RUNNING job, when StopRuntimeSession raises an exception,
        cancel_task returns a response containing job_id and status "CANCELLED".
        """
        job_id = record["job_id"]
        user_id = record["user_id"]

        async def mock_query(job_id, user_id):
            return record

        async def mock_update(job_id, user_id, status, **kwargs):
            pass

        mock_client = MagicMock()
        mock_client.stop_runtime_session = MagicMock(side_effect=exc)

        with patch(
            "container.code_mcp_server.query_job_record",
            side_effect=mock_query,
        ), patch(
            "container.code_mcp_server.update_job_status",
            side_effect=mock_update,
        ), patch(
            "boto3.client",
            return_value=mock_client,
        ), patch(
            "container.code_mcp_server._get_runtime_arn",
            return_value=self.FAKE_RUNTIME_ARN,
        ):
            result = await cancel_task(job_id=job_id, _user_id=user_id)

        # Must return success with job_id and CANCELLED status
        assert result["job_id"] == job_id
        assert result["status"] == "CANCELLED"

    @given(record=running_job_st, exc=exception_st)
    @settings(max_examples=100)
    @pytest.mark.asyncio
    async def test_update_job_status_called_despite_stop_session_failure(self, record, exc):
        """**Validates: Requirements 3.4**

        For any RUNNING job, when StopRuntimeSession raises an exception,
        cancel_task still calls update_job_status with status="CANCELLED".
        """
        job_id = record["job_id"]
        user_id = record["user_id"]

        async def mock_query(job_id, user_id):
            return record

        captured_updates = []

        async def mock_update(job_id, user_id, status, **kwargs):
            captured_updates.append({"job_id": job_id, "user_id": user_id, "status": status})

        mock_client = MagicMock()
        mock_client.stop_runtime_session = MagicMock(side_effect=exc)

        with patch(
            "container.code_mcp_server.query_job_record",
            side_effect=mock_query,
        ), patch(
            "container.code_mcp_server.update_job_status",
            side_effect=mock_update,
        ), patch(
            "boto3.client",
            return_value=mock_client,
        ), patch(
            "container.code_mcp_server._get_runtime_arn",
            return_value=self.FAKE_RUNTIME_ARN,
        ):
            await cancel_task(job_id=job_id, _user_id=user_id)

        # update_job_status must be called with status="CANCELLED"
        assert len(captured_updates) == 1
        assert captured_updates[0]["job_id"] == job_id
        assert captured_updates[0]["user_id"] == user_id
        assert captured_updates[0]["status"] == "CANCELLED"
