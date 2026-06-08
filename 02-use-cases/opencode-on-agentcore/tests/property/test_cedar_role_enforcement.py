# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property tests: Cedar role enforcement (v2).

Validates: Requirements 2.2, Correctness Property 2
- Readonly role denied run_coding_task and cancel_task for any repo_url
- Developer and admin roles allowed run_coding_task and cancel_task
- Production repo pattern denied for all roles
"""

from __future__ import annotations

import re

from hypothesis import given, settings
from hypothesis import strategies as st

# Cedar policy logic (mirrors stacks/policy_stack.py definitions)
READONLY_DENIED_TOOLS = {"run_coding_task", "cancel_task"}
PRODUCTION_REPO_PATTERN = re.compile(r".*-production$")

repo_urls = st.from_regex(r"https://github\.com/[a-z]{1,10}/[a-z]{1,20}", fullmatch=True)
roles = st.sampled_from(["admin", "developer", "readonly"])
tools = st.sampled_from(["run_coding_task", "get_task_status", "list_tasks", "cancel_task", "submit_input"])


def cedar_evaluate(role: str, tool: str, repo_url: str = "") -> bool:
    """Simulate Cedar policy evaluation. Returns True if ALLOWED."""
    if role == "readonly" and tool in READONLY_DENIED_TOOLS:
        return False
    if tool == "run_coding_task" and PRODUCTION_REPO_PATTERN.match(repo_url):
        return False
    return True


class TestCedarRoleEnforcement:
    """Property tests for Cedar policy evaluation."""

    @given(repo_url=repo_urls, tool=st.sampled_from(sorted(READONLY_DENIED_TOOLS)))
    @settings(max_examples=50)
    def test_readonly_denied_write_tools(self, repo_url, tool):
        """Readonly role is denied run_coding_task and cancel_task regardless of repo."""
        assert cedar_evaluate("readonly", tool, repo_url) is False

    @given(repo_url=repo_urls)
    @settings(max_examples=30)
    def test_readonly_allowed_read_tools(self, repo_url):
        """Readonly role is allowed get_task_status, list_tasks, submit_input."""
        for tool in ("get_task_status", "list_tasks", "submit_input"):
            assert cedar_evaluate("readonly", tool, repo_url) is True

    @given(role=st.sampled_from(["admin", "developer"]), tool=tools, repo_url=repo_urls)
    @settings(max_examples=50)
    def test_non_readonly_allowed_all_tools(self, role, tool, repo_url):
        """Admin and developer roles are allowed all tools (non-production repos)."""
        assert cedar_evaluate(role, tool, repo_url) is True

    @given(role=roles)
    @settings(max_examples=30)
    def test_production_repo_denied_for_all_roles(self, role):
        """No role can run_coding_task on *-production repos."""
        assert cedar_evaluate(role, "run_coding_task", "https://github.com/org/app-production") is False

    @given(role=st.sampled_from(["admin", "developer"]))
    @settings(max_examples=10)
    def test_non_production_repo_allowed(self, role):
        """Non-production repos are allowed for admin/developer."""
        assert cedar_evaluate(role, "run_coding_task", "https://github.com/org/app-staging") is True
