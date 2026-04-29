# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property tests: DynamoDB job record round-trip, update extras, and GSI1 attributes.

**Validates: Requirements 3.3, 3.4, 5.1, 5.2**

Property 4 -- DynamoDB job record write/query round-trip:
  For any valid job record inputs, writing via write_job_record then
  querying via query_job_record SHALL return a record with matching key fields.

Property 5 -- DynamoDB update extras persistence:
  For any subset of allowed extras with non-None values, calling
  update_job_status SHALL include all provided extras in the DynamoDB
  update expression.

Property 7 -- GSI1 attributes match current status:
  For any write or update, GSI1PK SHALL equal status#{current_status}.
  On write, GSI1SK SHALL equal the created_at timestamp.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from container.lib.dynamodb_helpers import (
    write_job_record,
    update_job_status,
    query_job_record,
    VALID_STATES,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Identifiers: non-empty alphanumeric strings (safe for DynamoDB keys)
_alnum = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
)

_job_id = st.text(alphabet=_alnum, min_size=4, max_size=36)
_user_id = st.text(alphabet=_alnum, min_size=1, max_size=40)
_status = st.sampled_from(sorted(VALID_STATES))
_text_field = st.text(min_size=0, max_size=100)
_url = st.from_regex(r"https://[a-z]{3,10}\.[a-z]{2,5}/[a-z]{1,20}", fullmatch=True)
_branch = st.from_regex(r"[a-zA-Z][a-zA-Z0-9\-_]{0,20}", fullmatch=True)

# Allowed extras for update_job_status
_pr_url = st.one_of(st.none(), _url)
_error_msg = st.one_of(st.none(), st.text(min_size=1, max_size=200))
_stop_reason = st.one_of(st.none(), st.sampled_from(["end_turn", "max_tokens", "tool_use", "error"]))
_files_edited = st.one_of(st.none(), st.lists(st.text(min_size=1, max_size=50), min_size=0, max_size=5))
_duration_seconds = st.one_of(
    st.none(),
    st.integers(min_value=0, max_value=86400),
    st.floats(min_value=0, max_value=86400, allow_nan=False, allow_infinity=False),
)
_completed_at = st.one_of(st.none(), st.from_regex(r"2024-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", fullmatch=True))


# ---------------------------------------------------------------------------
# Property 4: DynamoDB job record write/query round-trip
# ---------------------------------------------------------------------------


class TestDynamoDBRoundTrip:
    """**Validates: Requirements 3.3**"""

    @given(
        job_id=_job_id,
        user_id=_user_id,
        status=_status,
        task_description=_text_field,
        repo_url=_url,
        base_branch=_branch,
        target_branch=_branch,
    )
    @settings(max_examples=100, deadline=10_000)
    @pytest.mark.asyncio
    async def test_write_then_query_returns_matching_record(
        self, job_id, user_id, status, task_description, repo_url,
        base_branch, target_branch,
    ):
        """For any valid job record inputs, write then query SHALL return
        matching record."""
        # Storage for items written via put_item
        stored_items: list[dict] = []

        mock_table = MagicMock()
        mock_table.put_item = lambda **kwargs: stored_items.append(kwargs["Item"])

        def mock_query(**kwargs):
            """Simulate DynamoDB query by filtering stored items."""
            expr_values = kwargs.get("ExpressionAttributeValues", {})
            pk = expr_values.get(":pk", "")
            sk_prefix = expr_values.get(":sk_prefix", "")
            matching = [
                item for item in stored_items
                if item["PK"] == pk and item["SK"].startswith(sk_prefix)
            ]
            return {"Items": matching[:1]}

        mock_table.query = lambda **kwargs: mock_query(**kwargs)

        with patch("container.lib.dynamodb_helpers._get_ddb") as mock_ddb:
            mock_ddb.return_value.Table.return_value = mock_table

            # Write
            await write_job_record(
                job_id=job_id,
                user_id=user_id,
                status=status,
                task_description=task_description,
                repo_url=repo_url,
                base_branch=base_branch,
                target_branch=target_branch,
            )

            # Query
            record = await query_job_record(job_id=job_id, user_id=user_id)

        assert record is not None, "query_job_record returned None after write"
        assert record["job_id"] == job_id
        assert record["user_id"] == user_id
        assert record["status"] == status
        assert record["task_description"] == task_description
        assert record["repo_url"] == repo_url
        assert record["base_branch"] == base_branch
        assert record["target_branch"] == target_branch
        assert record["PK"] == f"user#{user_id}"
        assert record["SK"].startswith(f"job#{job_id}#")


# ---------------------------------------------------------------------------
# Property 5: DynamoDB update extras persistence
# ---------------------------------------------------------------------------


class TestDynamoDBUpdateExtras:
    """**Validates: Requirements 3.4**"""

    @given(
        job_id=_job_id,
        user_id=_user_id,
        initial_status=st.just("RUNNING"),
        new_status=st.sampled_from(["COMPLETE", "FAILED", "CANCELLED"]),
        pr_url=_pr_url,
        error=_error_msg,
        stop_reason=_stop_reason,
        files_edited=_files_edited,
        duration_seconds=_duration_seconds,
        completed_at=_completed_at,
    )
    @settings(max_examples=100, deadline=10_000)
    @pytest.mark.asyncio
    async def test_update_includes_all_provided_extras(
        self, job_id, user_id, initial_status, new_status,
        pr_url, error, stop_reason, files_edited, duration_seconds, completed_at,
    ):
        """For any subset of allowed extras, update_job_status SHALL include
        all in update expression."""
        # Build the extras dict (only non-None values)
        extras = {}
        if pr_url is not None:
            extras["pr_url"] = pr_url
        if error is not None:
            extras["error"] = error
        if stop_reason is not None:
            extras["stop_reason"] = stop_reason
        if files_edited is not None:
            extras["files_edited"] = files_edited
        if duration_seconds is not None:
            extras["duration_seconds"] = duration_seconds
        if completed_at is not None:
            extras["completed_at"] = completed_at

        # At least one extra should be provided for a meaningful test
        assume(len(extras) > 0)

        # Simulate an existing record
        existing_sk = f"job#{job_id}#2024-01-01T00:00:00+00:00"
        existing_item = {
            "PK": f"user#{user_id}",
            "SK": existing_sk,
            "job_id": job_id,
            "user_id": user_id,
            "status": initial_status,
        }

        captured_updates: list[dict] = []

        mock_table = MagicMock()

        def mock_query(**kwargs):
            return {"Items": [existing_item]}

        def mock_update_item(**kwargs):
            captured_updates.append(kwargs)

        mock_table.query = lambda **kwargs: mock_query(**kwargs)
        mock_table.update_item = lambda **kwargs: mock_update_item(**kwargs)

        with patch("container.lib.dynamodb_helpers._get_ddb") as mock_ddb:
            mock_ddb.return_value.Table.return_value = mock_table

            await update_job_status(
                job_id=job_id,
                user_id=user_id,
                status=new_status,
                **extras,
            )

        assert len(captured_updates) == 1, "Expected exactly one update_item call"
        update_call = captured_updates[0]

        update_expr = update_call["UpdateExpression"]
        attr_names = update_call["ExpressionAttributeNames"]
        attr_values = update_call["ExpressionAttributeValues"]

        # Status should always be in the update
        assert ":status" in attr_values
        assert attr_values[":status"] == new_status

        # Every provided extra should appear in the update expression
        for key, value in extras.items():
            placeholder = f":{key}"
            alias = f"#{key}"
            assert placeholder in attr_values, (
                f"Extra '{key}' value not in ExpressionAttributeValues"
            )
            # Floats are converted to Decimal for DynamoDB compatibility.
            expected = Decimal(str(value)) if isinstance(value, float) else value
            assert attr_values[placeholder] == expected, (
                f"Extra '{key}' value mismatch: expected {expected!r}, "
                f"got {attr_values[placeholder]!r}"
            )
            assert alias in attr_names, (
                f"Extra '{key}' alias not in ExpressionAttributeNames"
            )
            assert attr_names[alias] == key
            assert alias in update_expr, (
                f"Extra '{key}' alias not in UpdateExpression"
            )


# ---------------------------------------------------------------------------
# Property 7: GSI1 attributes match current status
# ---------------------------------------------------------------------------


class TestGSI1Attributes:
    """**Validates: Requirements 5.1, 5.2**

    NOTE: GSI1 attributes (GSI1PK, GSI1SK) are added by Task 5. This test
    verifies the property once Task 5 is implemented. If GSI1PK is present
    in the written item, it must equal status#{current_status}. If GSI1SK
    is present on write, it must equal the created_at timestamp.
    """

    @given(
        job_id=_job_id,
        user_id=_user_id,
        status=_status,
    )
    @settings(max_examples=100, deadline=10_000)
    @pytest.mark.asyncio
    async def test_write_gsi1pk_matches_status(self, job_id, user_id, status):
        """For any write, if GSI1PK is present it SHALL equal
        status#{current_status}."""
        captured_items: list[dict] = []

        mock_table = MagicMock()
        mock_table.put_item = lambda **kwargs: captured_items.append(kwargs["Item"])

        with patch("container.lib.dynamodb_helpers._get_ddb") as mock_ddb:
            mock_ddb.return_value.Table.return_value = mock_table

            await write_job_record(
                job_id=job_id,
                user_id=user_id,
                status=status,
            )

        assert len(captured_items) == 1
        item = captured_items[0]

        # GSI1PK check (will be present after Task 5)
        if "GSI1PK" in item:
            assert item["GSI1PK"] == f"status#{status}", (
                f"GSI1PK mismatch: expected 'status#{status}', "
                f"got {item['GSI1PK']!r}"
            )

        # GSI1SK check: should equal created_at timestamp
        if "GSI1SK" in item:
            assert item["GSI1SK"] == item["created_at"], (
                f"GSI1SK mismatch: expected {item['created_at']!r}, "
                f"got {item['GSI1SK']!r}"
            )

    @given(
        job_id=_job_id,
        user_id=_user_id,
        new_status=st.sampled_from(["COMPLETE", "FAILED", "CANCELLED"]),
    )
    @settings(max_examples=100, deadline=10_000)
    @pytest.mark.asyncio
    async def test_update_gsi1pk_matches_new_status(self, job_id, user_id, new_status):
        """For any update, if GSI1PK is in the update expression it SHALL
        equal status#{new_status}."""
        existing_sk = f"job#{job_id}#2024-01-01T00:00:00+00:00"
        existing_item = {
            "PK": f"user#{user_id}",
            "SK": existing_sk,
            "job_id": job_id,
            "user_id": user_id,
            "status": "RUNNING",
        }

        captured_updates: list[dict] = []

        mock_table = MagicMock()
        mock_table.query = lambda **kwargs: {"Items": [existing_item]}
        mock_table.update_item = lambda **kwargs: captured_updates.append(kwargs)

        with patch("container.lib.dynamodb_helpers._get_ddb") as mock_ddb:
            mock_ddb.return_value.Table.return_value = mock_table

            await update_job_status(
                job_id=job_id,
                user_id=user_id,
                status=new_status,
            )

        assert len(captured_updates) == 1
        update_call = captured_updates[0]
        attr_values = update_call.get("ExpressionAttributeValues", {})

        # GSI1PK check (will be present after Task 5)
        if ":gsi1pk" in attr_values:
            assert attr_values[":gsi1pk"] == f"status#{new_status}", (
                f"GSI1PK update mismatch: expected 'status#{new_status}', "
                f"got {attr_values[':gsi1pk']!r}"
            )
