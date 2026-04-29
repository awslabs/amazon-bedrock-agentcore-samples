# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property test: Git push retry count.

**Validates: Requirements 10.1, 10.2, 10.3**

Property 9 — Git push retry count:
  For any sequence of consecutive push failures, verify exactly 3 attempts
  with fetch+rebase between retries before error propagation. When push
  succeeds on attempt N (1-3), verify no more retries happen.
"""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, call, patch

from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Stub strands before importing the module under test
_strands_mock = MagicMock()
_strands_mock.tool = lambda fn: fn
sys.modules.setdefault("strands", _strands_mock)

from container.tools.git_push_and_create_pr import git_push_and_create_pr

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Branch names: 1-60 chars of safe branch characters
_branch_char = st.sampled_from(
    list("abcdefghijklmnopqrstuvwxyz0123456789-_/")
)
_branch_name = st.text(alphabet=_branch_char, min_size=1, max_size=60)

# Job IDs: simple alphanumeric + hyphens
_job_id = st.from_regex(r"[a-f0-9\-]{8,36}", fullmatch=True)

# Repo URLs
_repo_url = st.sampled_from([
    "https://github.com/owner/repo",
    "https://github.com/org/project.git",
    "https://github.com/user/my-app",
])

# Task descriptions
_task_desc = st.text(min_size=1, max_size=100, alphabet=st.characters(
    whitelist_categories=("L", "N", "Z"),
))

# Token
_token = st.from_regex(r"ghp_[a-zA-Z0-9]{20,36}", fullmatch=True)

# Work directory
_work_dir = st.sampled_from(["/tmp/work", "/workspace/code", "/home/user/repo"])


def _make_subprocess_side_effect(*, push_fail_count: int):
    """Build a side_effect function for subprocess.run that simulates push failures.

    - git add -A: always succeeds
    - git diff --cached --stat: returns non-empty output (changes exist)
    - git commit: always succeeds
    - git push: fails `push_fail_count` times, then succeeds
    - git fetch / git rebase: always succeed
    """
    push_attempts = 0

    def side_effect(cmd, **kwargs):
        nonlocal push_attempts

        if cmd[0] != "git":
            return MagicMock(returncode=0, stdout="", stderr="")

        subcmd = cmd[1] if len(cmd) > 1 else ""

        if subcmd == "add":
            return MagicMock(returncode=0, stdout="", stderr="")

        if subcmd == "diff":
            result = MagicMock()
            result.stdout = " file.py | 10 +++++++---\n 1 file changed"
            result.stderr = ""
            result.returncode = 0
            result.strip = lambda: result.stdout.strip()
            return result

        if subcmd == "commit":
            return MagicMock(returncode=0, stdout="", stderr="")

        if subcmd == "push":
            push_attempts += 1
            if push_attempts <= push_fail_count:
                if kwargs.get("check", False):
                    raise subprocess.CalledProcessError(1, cmd)
                return MagicMock(returncode=1)
            return MagicMock(returncode=0, stdout="", stderr="")

        if subcmd == "fetch":
            return MagicMock(returncode=0, stdout="", stderr="")

        if subcmd == "rebase":
            return MagicMock(returncode=0, stdout="", stderr="")

        # curl for PR creation
        if cmd[0] == "curl" or subcmd == "curl":
            return MagicMock(returncode=0, stdout='{"html_url": "https://github.com/o/r/pull/1"}', stderr="")

        return MagicMock(returncode=0, stdout="", stderr="")

    return side_effect



# ---------------------------------------------------------------------------
# Property 9a: All 3 push attempts fail → error propagated
# ---------------------------------------------------------------------------


class TestPushAllFailProperty:
    """**Validates: Requirements 10.2, 10.3**"""

    @given(
        work_dir=_work_dir,
        token=_token,
        repo_url=_repo_url,
        target_branch=_branch_name,
        base_branch=_branch_name,
        task_desc=_task_desc,
        job_id=_job_id,
    )
    @settings(max_examples=100, deadline=10_000)
    def test_exactly_3_push_attempts_then_error(
        self, work_dir, token, repo_url, target_branch, base_branch, task_desc, job_id
    ):
        """When push always fails, exactly 3 attempts are made and CalledProcessError propagates."""
        side_effect = _make_subprocess_side_effect(push_fail_count=999)

        with patch("container.tools.git_push_and_create_pr.subprocess.run", side_effect=side_effect) as mock_run:
            raised = False
            try:
                git_push_and_create_pr(
                    work_dir=work_dir,
                    token=token,
                    repo_url=repo_url,
                    target_branch=target_branch,
                    base_branch=base_branch,
                    task_description=task_desc,
                    job_id=job_id,
                )
            except subprocess.CalledProcessError:
                raised = True

            assert raised, "CalledProcessError should be propagated after 3 failures"

            # Count push attempts
            push_calls = [
                c for c in mock_run.call_args_list
                if len(c[0]) > 0 and len(c[0][0]) > 1 and c[0][0][1] == "push"
            ]
            assert len(push_calls) == 3, f"Expected 3 push attempts, got {len(push_calls)}"


# ---------------------------------------------------------------------------
# Property 9b: Fetch+rebase called between retries (2 times for 3 attempts)
# ---------------------------------------------------------------------------


class TestFetchRebaseBetweenRetriesProperty:
    """**Validates: Requirements 10.1, 10.2**"""

    @given(
        work_dir=_work_dir,
        token=_token,
        repo_url=_repo_url,
        target_branch=_branch_name,
        base_branch=_branch_name,
        task_desc=_task_desc,
        job_id=_job_id,
    )
    @settings(max_examples=100, deadline=10_000)
    def test_fetch_rebase_between_retries(
        self, work_dir, token, repo_url, target_branch, base_branch, task_desc, job_id
    ):
        """Between each push retry, fetch+rebase is called. For 3 push attempts, that's 2 fetch+rebase pairs."""
        side_effect = _make_subprocess_side_effect(push_fail_count=999)

        with patch("container.tools.git_push_and_create_pr.subprocess.run", side_effect=side_effect) as mock_run:
            try:
                git_push_and_create_pr(
                    work_dir=work_dir,
                    token=token,
                    repo_url=repo_url,
                    target_branch=target_branch,
                    base_branch=base_branch,
                    task_description=task_desc,
                    job_id=job_id,
                )
            except subprocess.CalledProcessError:
                pass

            fetch_calls = [
                c for c in mock_run.call_args_list
                if len(c[0]) > 0 and len(c[0][0]) > 1 and c[0][0][1] == "fetch"
            ]
            rebase_calls = [
                c for c in mock_run.call_args_list
                if len(c[0]) > 0 and len(c[0][0]) > 1 and c[0][0][1] == "rebase"
            ]

            assert len(fetch_calls) == 2, f"Expected 2 fetch calls, got {len(fetch_calls)}"
            assert len(rebase_calls) == 2, f"Expected 2 rebase calls, got {len(rebase_calls)}"

            # Verify ordering: each fetch+rebase pair comes after a push failure
            all_git_cmds = [
                c[0][0][1] for c in mock_run.call_args_list
                if len(c[0]) > 0 and len(c[0][0]) > 1 and c[0][0][0] == "git"
            ]

            # Expected sequence: add, diff, commit, push, fetch, rebase, push, fetch, rebase, push
            push_indices = [i for i, cmd in enumerate(all_git_cmds) if cmd == "push"]
            fetch_indices = [i for i, cmd in enumerate(all_git_cmds) if cmd == "fetch"]
            rebase_indices = [i for i, cmd in enumerate(all_git_cmds) if cmd == "rebase"]

            # Each fetch should come after a push and before the next push
            for fi, ri in zip(fetch_indices, rebase_indices):
                assert fi < ri, "fetch should come before rebase"
                # There should be a push before this fetch
                preceding_pushes = [p for p in push_indices if p < fi]
                assert len(preceding_pushes) > 0, "fetch should follow a failed push"


# ---------------------------------------------------------------------------
# Property 9c: Push succeeds on attempt N (1-3) → no more retries
# ---------------------------------------------------------------------------


class TestPushSuccessStopsRetryProperty:
    """**Validates: Requirements 10.1, 10.2**"""

    @given(
        succeed_on=st.integers(min_value=1, max_value=3),
        work_dir=_work_dir,
        token=_token,
        repo_url=_repo_url,
        target_branch=_branch_name,
        base_branch=_branch_name,
        task_desc=_task_desc,
        job_id=_job_id,
    )
    @settings(max_examples=100, deadline=10_000)
    def test_push_success_stops_retries(
        self, succeed_on, work_dir, token, repo_url, target_branch, base_branch, task_desc, job_id
    ):
        """When push succeeds on attempt N, exactly N push calls are made and no error is raised."""
        # Push fails (succeed_on - 1) times, then succeeds
        side_effect = _make_subprocess_side_effect(push_fail_count=succeed_on - 1)

        with patch("container.tools.git_push_and_create_pr.subprocess.run", side_effect=side_effect) as mock_run:
            result = git_push_and_create_pr(
                work_dir=work_dir,
                token=token,
                repo_url=repo_url,
                target_branch=target_branch,
                base_branch=base_branch,
                task_description=task_desc,
                job_id=job_id,
            )

            # Should not raise — push eventually succeeded
            assert result["pushed"] is True

            push_calls = [
                c for c in mock_run.call_args_list
                if len(c[0]) > 0 and len(c[0][0]) > 1 and c[0][0][1] == "push"
            ]
            assert len(push_calls) == succeed_on, (
                f"Expected {succeed_on} push attempts, got {len(push_calls)}"
            )

            # Fetch+rebase should be called (succeed_on - 1) times
            fetch_calls = [
                c for c in mock_run.call_args_list
                if len(c[0]) > 0 and len(c[0][0]) > 1 and c[0][0][1] == "fetch"
            ]
            rebase_calls = [
                c for c in mock_run.call_args_list
                if len(c[0]) > 0 and len(c[0][0]) > 1 and c[0][0][1] == "rebase"
            ]
            expected_rebase_count = succeed_on - 1
            assert len(fetch_calls) == expected_rebase_count, (
                f"Expected {expected_rebase_count} fetch calls, got {len(fetch_calls)}"
            )
            assert len(rebase_calls) == expected_rebase_count, (
                f"Expected {expected_rebase_count} rebase calls, got {len(rebase_calls)}"
            )
