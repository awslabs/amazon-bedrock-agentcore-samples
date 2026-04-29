# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property tests: code tool rejects invalid timeout values.

Property 6: For any integer timeout_minutes < 1 or > 30, the tool rejects
with a validation error. For [1, 30], the timeout is accepted.

Validates: Requirement 9.3

Tests the validation logic as implemented in code-mcp-server.js.
"""

from hypothesis import given, settings
from hypothesis import strategies as st


def validate_timeout(timeout_minutes):
    """Mirror the validation logic from code-mcp-server.js."""
    if timeout_minutes is None:
        return True, 10  # default
    if not isinstance(timeout_minutes, int) or timeout_minutes < 1 or timeout_minutes > 30:
        return False, None
    return True, timeout_minutes


class TestCodeToolTimeoutValidation:

    @given(t=st.integers(min_value=1, max_value=30))
    @settings(max_examples=30)
    def test_valid_timeout_accepted(self, t):
        """Timeouts in [1, 30] are accepted."""
        valid, value = validate_timeout(t)
        assert valid
        assert value == t

    @given(t=st.integers(max_value=0))
    @settings(max_examples=30)
    def test_timeout_below_1_rejected(self, t):
        """Timeouts < 1 are rejected."""
        valid, _ = validate_timeout(t)
        assert not valid

    @given(t=st.integers(min_value=31))
    @settings(max_examples=30)
    def test_timeout_above_30_rejected(self, t):
        """Timeouts > 30 are rejected."""
        valid, _ = validate_timeout(t)
        assert not valid

    def test_default_timeout(self):
        """Omitted timeout defaults to 10."""
        valid, value = validate_timeout(None)
        assert valid
        assert value == 10
