# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Integration test: ``list_tasks`` with status filter and user scoping.

Creates multiple tasks with different statuses, verifies filtering works.
Verifies user A cannot see user B's tasks.

Requirements: 6.2, 6.3, 6.4, 20.1
"""

from __future__ import annotations

import sys
import uuid
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
    list_tasks,
    get_task_status,
)
from container.lib.dynamodb_helpers import query_user_jobs  # noqa: E402


# ---------------------------------------------------------------------------
# Fake DynamoDB data
# ---------------------------------------------------------------------------
_FAKE_JOBS_USER_A = [
    {"PK": "user#alice", "SK": f"job#{uuid.uuid4()}#2025-01-01T00:00:00+00:00",
     "job_id": str(uuid.uuid4()), "status": "COMPLETE", "user_id": "alice"},
    {"PK": "user#alice", "SK": f"job#{uuid.uuid4()}#2025-01-02T00:00:00+00:00",
     "job_id": str(uuid.uuid4()), "status": "RUNNING", "user_id": "alice"},
    {"PK": "user#alice", "SK": f"job#{uuid.uuid4()}#2025-01-03T00:00:00+00:00",
     "job_id": str(uuid.uuid4()), "status": "FAILED", "user_id": "alice"},
    {"PK": "user#alice", "SK": f"job#{uuid.uuid4()}#2025-01-04T00:00:00+00:00",
     "job_id": str(uuid.uuid4()), "status": "CANCELLED", "user_id": "alice"},
]

_FAKE_JOBS_USER_B = [
    {"PK": "user#bob", "SK": f"job#{uuid.uuid4()}#2025-01-01T00:00:00+00:00",
     "job_id": str(uuid.uuid4()), "status": "COMPLETE", "user_id": "bob"},
]


def _mock_query_for_user(user_id):
    """Return a mock DynamoDB query function scoped to a user."""
    data = {
        "alice": _FAKE_JOBS_USER_A,
        "bob": _FAKE_JOBS_USER_B,
    }
    user_jobs = data.get(user_id, [])

    def mock_query(**kwargs):
        pk = kwargs["ExpressionAttributeValues"][":pk"]
        expected_pk = f"user#{user_id}"
        if pk != expected_pk:
            return {"Items": []}

        items = user_jobs
        # Apply status filter if present
        sf = kwargs.get("ExpressionAttributeValues", {}).get(":sf")
        if sf:
            items = [j for j in items if j["status"] == sf]

        limit = kwargs.get("Limit", 50)
        return {"Items": items[:limit]}

    return mock_query


class TestListTasks:
    @pytest.mark.asyncio
    async def test_list_returns_all_user_jobs(self):
        """Verify list_tasks returns all jobs for the user (Req 6.2)."""
        mock_table = MagicMock()
        mock_table.query = _mock_query_for_user("alice")

        with patch("container.lib.dynamodb_helpers._get_ddb") as mock_ddb:
            mock_ddb.return_value.Table.return_value = mock_table
            result = await list_tasks(_user_id="alice")

        assert result["count"] == 4
        assert len(result["jobs"]) == 4

    @pytest.mark.asyncio
    async def test_status_filter_returns_matching_only(self):
        """Verify status filter returns only matching jobs (Req 6.3)."""
        mock_table = MagicMock()
        mock_table.query = _mock_query_for_user("alice")

        with patch("container.lib.dynamodb_helpers._get_ddb") as mock_ddb:
            mock_ddb.return_value.Table.return_value = mock_table
            result = await list_tasks(status="COMPLETE", _user_id="alice")

        assert result["count"] == 1
        assert all(j["status"] == "COMPLETE" for j in result["jobs"])

    @pytest.mark.asyncio
    async def test_limit_capped_at_100(self):
        """Verify limit > 100 is capped to 100 (Req 6.4)."""
        captured_kwargs = []
        mock_table = MagicMock()

        def capture_query(**kwargs):
            captured_kwargs.append(kwargs)
            return {"Items": []}

        mock_table.query = capture_query

        with patch("container.lib.dynamodb_helpers._get_ddb") as mock_ddb:
            mock_ddb.return_value.Table.return_value = mock_table
            await list_tasks(limit=500, _user_id="alice")

        assert captured_kwargs[0]["Limit"] <= 100

    @pytest.mark.asyncio
    async def test_user_a_cannot_see_user_b_tasks(self):
        """Verify user scoping: alice cannot see bob's tasks (Req 20.1)."""
        mock_table = MagicMock()
        # Alice's query returns alice's data only
        mock_table.query = _mock_query_for_user("alice")

        with patch("container.lib.dynamodb_helpers._get_ddb") as mock_ddb:
            mock_ddb.return_value.Table.return_value = mock_table
            result = await list_tasks(_user_id="alice")

        # All returned jobs belong to alice
        for job in result["jobs"]:
            assert job["user_id"] == "alice"

    @pytest.mark.asyncio
    async def test_get_task_status_not_found(self):
        """Verify get_task_status returns error for non-existent job."""
        with patch(
            "container.code_mcp_server.query_job_record",
            new_callable=AsyncMock,
            return_value=None,
        ):
            result = await get_task_status(job_id="nonexistent", _user_id="alice")

        assert "error" in result
        assert "not found" in result["error"].lower()
