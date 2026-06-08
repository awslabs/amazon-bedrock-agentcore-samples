# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property tests: PR creation token isolation and URL extraction.

**Validates: Requirements 2.2, 2.3**

Property 2 -- PR creation token isolation:
  For any valid OAuth token, when git_push_and_create_pr creates a pull
  request, the token SHALL NOT appear in any command-line argument passed
  to any subprocess call.

Property 3 -- PR URL extraction from API response:
  For any valid GitHub API response containing an html_url field,
  git_push_and_create_pr SHALL return that URL in the pr_url field of
  the result.
"""

from __future__ import annotations

import json
import sys
from io import BytesIO
from unittest.mock import patch, MagicMock, PropertyMock

# Stub strands before importing the module under test
strands_mock = MagicMock()
strands_mock.tool = lambda fn: fn
sys.modules.setdefault("strands", strands_mock)

from hypothesis import given, settings
from hypothesis import strategies as st

from container.tools.git_push_and_create_pr import git_push_and_create_pr

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# OAuth tokens: realistic tokens with distinctive prefixes
_token_prefix = st.sampled_from(["ghp_", "gho_", "ghs_", "ghu_", "tok_"])
_token_body = st.text(
    alphabet=st.sampled_from(
        list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    ),
    min_size=20,
    max_size=80,
)


@st.composite
def _oauth_token_strategy(draw):
    return draw(_token_prefix) + draw(_token_body)


_oauth_token = _oauth_token_strategy()

# GitHub-style owner/repo path segments
_path_segment = st.from_regex(r"[a-zA-Z][a-zA-Z0-9\-]{2,38}", fullmatch=True)

# PR URLs: valid GitHub PR URLs
_pr_number = st.integers(min_value=1, max_value=99999)


@st.composite
def _html_url_strategy(draw):
    owner = draw(_path_segment)
    repo = draw(_path_segment)
    num = draw(_pr_number)
    return f"https://github.com/{owner}/{repo}/pull/{num}"


_html_url = _html_url_strategy()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_subprocess_mock():
    """Create a subprocess.run mock that simulates successful git operations."""
    mock = MagicMock()
    # git diff --cached --stat returns non-empty output (changes exist)
    diff_result = MagicMock()
    diff_result.stdout = "file.py | 1 +\n"

    def side_effect(cmd, **kwargs):
        if cmd[1:3] == ["diff", "--cached"]:
            return diff_result
        return MagicMock()

    mock.side_effect = side_effect
    return mock


def _make_urlopen_mock(response_body: dict):
    """Create a urlopen mock that returns a given JSON response."""
    resp_mock = MagicMock()
    resp_mock.read.return_value = json.dumps(response_body).encode()
    return resp_mock


# ---------------------------------------------------------------------------
# Property 2: PR creation token isolation
# ---------------------------------------------------------------------------


class TestPRCreationTokenIsolation:
    """**Validates: Requirements 2.2**"""

    @given(token=_oauth_token)
    @settings(max_examples=100, deadline=5_000)
    def test_token_not_in_any_subprocess_args(self, token):
        """For any token, token SHALL NOT appear in any subprocess args."""
        subprocess_mock = _make_subprocess_mock()
        urlopen_response = _make_urlopen_mock(
            {"html_url": "https://github.com/owner/repo/pull/1"}
        )

        with (
            patch(
                "container.tools.git_push_and_create_pr.subprocess.run",
                subprocess_mock,
            ),
            patch(
                "container.tools.git_push_and_create_pr.urllib.request.urlopen",
                return_value=urlopen_response,
            ),
        ):
            result = git_push_and_create_pr(
                work_dir="/tmp/work",
                token=token,
                repo_url="https://github.com/test-owner/test-repo",
                target_branch="feature-branch",
                base_branch="main",
                task_description="Test task",
                job_id="job-123",
            )

            # Token SHALL NOT appear in any command-line argument
            for call_obj in subprocess_mock.call_args_list:
                cmd_args = call_obj[0][0]
                for arg in cmd_args:
                    assert token not in arg, (
                        f"Token '{token}' found in subprocess arg: {arg}"
                    )


# ---------------------------------------------------------------------------
# Property 3: PR URL extraction from API response
# ---------------------------------------------------------------------------


class TestPRURLExtraction:
    """**Validates: Requirements 2.3**"""

    @given(html_url=_html_url)
    @settings(max_examples=100, deadline=5_000)
    def test_html_url_returned_in_pr_url(self, html_url):
        """For any valid API response with html_url, the URL SHALL be
        returned in pr_url."""
        subprocess_mock = _make_subprocess_mock()
        urlopen_response = _make_urlopen_mock({"html_url": html_url})

        with (
            patch(
                "container.tools.git_push_and_create_pr.subprocess.run",
                subprocess_mock,
            ),
            patch(
                "container.tools.git_push_and_create_pr.urllib.request.urlopen",
                return_value=urlopen_response,
            ),
        ):
            result = git_push_and_create_pr(
                work_dir="/tmp/work",
                token="ghp_testtoken1234567890abcdef",
                repo_url="https://github.com/test-owner/test-repo",
                target_branch="feature-branch",
                base_branch="main",
                task_description="Test task",
                job_id="job-123",
            )

            assert result["pr_url"] == html_url, (
                f"Expected pr_url={html_url!r}, got {result['pr_url']!r}"
            )
            assert result["pushed"] is True
