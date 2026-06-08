# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property test: GIT_ASKPASS token isolation.

**Validates: Requirements 1.1, 1.2, 1.4**

Property 1 -- GIT_ASKPASS token isolation:
  For any valid OAuth token and repository URL, when git_clone is called,
  the token SHALL NOT appear in any command-line argument passed to
  subprocess.run, and the GIT_ASKPASS environment variable SHALL be set
  in the subprocess environment.
"""

from __future__ import annotations

import sys
from unittest.mock import patch, MagicMock

# Stub strands before importing the module under test
strands_mock = MagicMock()
strands_mock.tool = lambda fn: fn
sys.modules.setdefault("strands", strands_mock)

from hypothesis import given, settings
from hypothesis import strategies as st

from container.tools.git_clone import git_clone

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# OAuth tokens: realistic tokens with a distinctive prefix so they won't
# accidentally appear as substrings of URL path segments.
# Real GitHub tokens look like ghp_XXXX (36+ chars), so we use a prefix
# that cannot appear in a URL host or path component.
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

# Git host domains
_git_host = st.sampled_from([
    "github.com",
    "bitbucket.org",
    "git.example.com",
])


@st.composite
def _repo_url(draw):
    host = draw(_git_host)
    owner = draw(_path_segment)
    repo = draw(_path_segment)
    return f"https://{host}/{owner}/{repo}"


_branch_name = st.from_regex(r"[a-zA-Z][a-zA-Z0-9\-_]{0,20}", fullmatch=True)

# Optional sparse paths
_sparse_paths = st.one_of(
    st.none(),
    st.lists(
        st.from_regex(r"[a-zA-Z][a-zA-Z0-9_/]{0,20}", fullmatch=True),
        min_size=1,
        max_size=5,
    ),
)


# ---------------------------------------------------------------------------
# Property 1: GIT_ASKPASS token isolation
# ---------------------------------------------------------------------------


class TestGitAskpassTokenIsolation:
    """**Validates: Requirements 1.1, 1.2, 1.4**"""

    @given(
        token=_oauth_token,
        repo_url=_repo_url(),
        branch=_branch_name,
        sparse_paths=_sparse_paths,
    )
    @settings(max_examples=100, deadline=5_000)
    def test_token_not_in_subprocess_args_and_askpass_set(
        self, token, repo_url, branch, sparse_paths
    ):
        """For any token and repo URL, token SHALL NOT appear in subprocess
        args and GIT_ASKPASS SHALL be set in the subprocess environment."""
        with (
            patch("container.tools.git_clone.subprocess.run") as mock_run,
            patch(
                "container.tools.git_clone._create_askpass_script",
                return_value="/tmp/fake_askpass.sh",
            ),
            patch("container.tools.git_clone.os.path.exists", return_value=True),
            patch("container.tools.git_clone.os.remove"),
        ):
            git_clone(
                repo_url=repo_url,
                token=token,
                base_branch=branch,
                work_dir="/tmp/work",
                sparse_paths=sparse_paths,
            )

            # Check every subprocess.run call
            for call_obj in mock_run.call_args_list:
                cmd_args = call_obj[0][0]
                env = call_obj[1].get("env", {})

                # Token SHALL NOT appear in any command-line argument
                for arg in cmd_args:
                    assert token not in arg, (
                        f"Token '{token}' found in subprocess arg: {arg}"
                    )

                # GIT_ASKPASS SHALL be set in the subprocess environment
                assert "GIT_ASKPASS" in env, (
                    "GIT_ASKPASS not set in subprocess environment"
                )
