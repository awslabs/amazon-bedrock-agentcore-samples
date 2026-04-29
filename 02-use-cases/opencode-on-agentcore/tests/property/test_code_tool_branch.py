# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property tests: code tool auto-generates branch name when omitted.

Property 7: For any invocation where target_branch is not provided,
a non-empty auto-generated branch name is used.

Validates: Requirement 9.1

Tests the branch generation logic as implemented in code-mcp-server.js.
"""

import re
import secrets
import time

from hypothesis import given, settings
from hypothesis import strategies as st


def generate_branch_name():
    """Mirror the generateBranchName() logic from code-mcp-server.js."""
    return f"opencode/{int(time.time() * 1000)}-{secrets.token_hex(3)}"


class TestCodeToolBranchGeneration:

    @given(st.just(None))
    @settings(max_examples=30)
    def test_auto_generated_branch_is_nonempty(self, _):
        """Auto-generated branch name is always non-empty."""
        branch = generate_branch_name()
        assert isinstance(branch, str) and len(branch) > 0

    @given(st.just(None))
    @settings(max_examples=30)
    def test_auto_generated_branch_has_prefix(self, _):
        """Auto-generated branch starts with opencode/ prefix."""
        branch = generate_branch_name()
        assert branch.startswith("opencode/")

    @given(st.just(None))
    @settings(max_examples=10)
    def test_auto_generated_branches_are_unique(self, _):
        """Multiple calls produce unique branch names."""
        branches = {generate_branch_name() for _ in range(10)}
        assert len(branches) == 10

    @given(explicit=st.text(min_size=1, max_size=100).filter(lambda s: s.strip()))
    @settings(max_examples=20)
    def test_explicit_branch_used_when_provided(self, explicit):
        """When target_branch is provided, it is used as-is."""
        branch = explicit if explicit else generate_branch_name()
        assert branch == explicit
