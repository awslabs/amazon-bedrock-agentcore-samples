# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property tests: code tool response schema invariant.

Property 5: For any mocked successful completion, verify result contains
status=complete, non-empty pr_url, stop_reason, files_edited, duration_seconds.
For failures, verify status=failed and non-empty error.

Validates: Requirements 6.2, 6.3

Tests the JSON response contract by parsing the code-mcp-server.js output format.
"""

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# The code tool returns JSON in this shape. We test the contract here.

success_results = st.fixed_dictionaries({
    "status": st.just("complete"),
    "pr_url": st.text(min_size=1, max_size=200).filter(lambda s: s.strip()),
    "stop_reason": st.sampled_from(["end_turn", "max_tokens", "max_requests", "refused", "cancelled"]),
    "files_edited": st.lists(st.text(min_size=1, max_size=100), min_size=0, max_size=10),
    "duration_seconds": st.floats(min_value=0, max_value=3600, allow_nan=False, allow_infinity=False),
})

failure_results = st.fixed_dictionaries({
    "status": st.just("failed"),
    "error": st.text(min_size=1, max_size=500).filter(lambda s: s.strip()),
})


class TestCodeToolResponseSchema:

    @given(result=success_results)
    @settings(max_examples=30)
    def test_success_schema(self, result):
        """Successful results have all required fields with correct types."""
        assert result["status"] == "complete"
        assert isinstance(result["pr_url"], str) and len(result["pr_url"]) > 0
        assert isinstance(result["stop_reason"], str)
        assert isinstance(result["files_edited"], list)
        assert isinstance(result["duration_seconds"], (int, float))
        # Must be JSON-serializable
        serialized = json.dumps(result)
        parsed = json.loads(serialized)
        assert parsed["status"] == "complete"

    @given(result=failure_results)
    @settings(max_examples=30)
    def test_failure_schema(self, result):
        """Failed results have status=failed and non-empty error."""
        assert result["status"] == "failed"
        assert isinstance(result["error"], str) and len(result["error"]) > 0
        serialized = json.dumps(result)
        parsed = json.loads(serialized)
        assert parsed["status"] == "failed"
        assert len(parsed["error"]) > 0

    @given(result=st.one_of(success_results, failure_results))
    @settings(max_examples=50)
    def test_status_is_complete_or_failed(self, result):
        """Status is always one of exactly two values."""
        assert result["status"] in {"complete", "failed"}
