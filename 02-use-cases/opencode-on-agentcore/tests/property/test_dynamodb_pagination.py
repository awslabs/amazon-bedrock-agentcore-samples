# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property test: DynamoDB pagination with status filter.

**Validates: Requirements 13.1, 13.3**

Property 10 -- Pagination returns all matching jobs:
  For any user with N jobs matching a given status filter where N <= limit,
  query_user_jobs with that status_filter SHALL return all N matching jobs,
  even when matching items span multiple DynamoDB query pages.
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from container.lib.dynamodb_helpers import query_user_jobs, VALID_STATES

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_alnum = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
)
_user_id = st.text(alphabet=_alnum, min_size=1, max_size=20)
_status = st.sampled_from(sorted(VALID_STATES))
_limit = st.integers(min_value=1, max_value=50)

# Number of matching and non-matching jobs
_n_matching = st.integers(min_value=0, max_value=30)
_n_non_matching = st.integers(min_value=0, max_value=30)

# Page size for simulated DynamoDB responses (how many scanned items per page)
_page_size = st.integers(min_value=1, max_value=10)


def _make_job_item(user_id: str, job_index: int, status: str) -> dict:
    """Create a fake DynamoDB job item."""
    return {
        "PK": f"user#{user_id}",
        "SK": f"job#job{job_index:04d}#2024-01-01T00:{job_index:02d}:00+00:00",
        "job_id": f"job{job_index:04d}",
        "user_id": user_id,
        "status": status,
        "created_at": f"2024-01-01T00:{job_index:02d}:00+00:00",
    }


def _build_mock_table(all_items: list[dict], page_size: int) -> MagicMock:
    """Build a mock DynamoDB table that simulates pagination.

    The mock splits *all_items* into pages of *page_size* scanned items.
    It applies the FilterExpression client-side (matching the real DynamoDB
    behaviour where Limit caps scanned items, not returned items).
    """
    mock_table = MagicMock()

    def mock_query(**kwargs):
        limit = kwargs.get("Limit", len(all_items))
        start_key = kwargs.get("ExclusiveStartKey")

        # Determine the starting index from the pagination key.
        start_idx = 0
        if start_key:
            start_idx = start_key.get("_idx", 0)

        # DynamoDB scans up to `Limit` items from the partition, then
        # applies the filter.  We simulate this by slicing all_items.
        scan_end = min(start_idx + min(limit, page_size), len(all_items))
        scanned = all_items[start_idx:scan_end]

        # Apply filter expression if present.
        filter_expr = kwargs.get("FilterExpression")
        if filter_expr:
            expr_values = kwargs.get("ExpressionAttributeValues", {})
            target_status = expr_values.get(":sf")
            returned = [item for item in scanned if item["status"] == target_status]
        else:
            returned = scanned

        resp: dict[str, Any] = {"Items": returned}

        # If there are more items to scan, include LastEvaluatedKey.
        if scan_end < len(all_items):
            resp["LastEvaluatedKey"] = {"_idx": scan_end}

        return resp

    mock_table.query = mock_query
    return mock_table


# ---------------------------------------------------------------------------
# Property 10: Pagination returns all matching jobs
# ---------------------------------------------------------------------------


class TestDynamoDBPagination:
    """**Validates: Requirements 13.1, 13.3**"""

    @given(
        user_id=_user_id,
        target_status=_status,
        n_matching=_n_matching,
        n_non_matching=_n_non_matching,
        limit=_limit,
        page_size=_page_size,
    )
    @settings(max_examples=100, deadline=30_000)
    @pytest.mark.asyncio
    async def test_pagination_returns_all_matching_jobs_within_limit(
        self,
        user_id: str,
        target_status: str,
        n_matching: int,
        n_non_matching: int,
        limit: int,
        page_size: int,
    ):
        """For any user with N matching jobs where N <= limit,
        query_user_jobs SHALL return all N matching jobs."""
        # Only test the case where matching count is within the limit.
        assume(n_matching <= limit)
        # Need at least some items to make the test meaningful.
        assume(n_matching + n_non_matching > 0)

        # Pick a different status for non-matching items.
        other_statuses = sorted(VALID_STATES - {target_status})
        other_status = other_statuses[0] if other_statuses else target_status
        # If target_status is the only valid status, skip non-matching items.
        if other_status == target_status:
            n_non_matching = 0

        # Build the dataset: interleave matching and non-matching items.
        all_items: list[dict] = []
        idx = 0
        match_idx = 0
        non_match_idx = 0
        while match_idx < n_matching or non_match_idx < n_non_matching:
            # Alternate: add a non-matching item, then a matching item.
            if non_match_idx < n_non_matching:
                all_items.append(_make_job_item(user_id, idx, other_status))
                idx += 1
                non_match_idx += 1
            if match_idx < n_matching:
                all_items.append(_make_job_item(user_id, idx, target_status))
                idx += 1
                match_idx += 1

        mock_table = _build_mock_table(all_items, page_size)

        with patch("container.lib.dynamodb_helpers._get_ddb") as mock_ddb:
            mock_ddb.return_value.Table.return_value = mock_table

            result = await query_user_jobs(
                user_id=user_id,
                status_filter=target_status,
                limit=limit,
            )

        returned_jobs = result["jobs"]
        returned_count = result["count"]

        # All returned jobs must have the target status.
        for job in returned_jobs:
            assert job["status"] == target_status, (
                f"Returned job has status {job['status']!r}, "
                f"expected {target_status!r}"
            )

        # Since N <= limit, ALL matching jobs must be returned.
        assert returned_count == n_matching, (
            f"Expected {n_matching} matching jobs, got {returned_count}. "
            f"page_size={page_size}, total_items={len(all_items)}, limit={limit}"
        )
        assert len(returned_jobs) == n_matching
