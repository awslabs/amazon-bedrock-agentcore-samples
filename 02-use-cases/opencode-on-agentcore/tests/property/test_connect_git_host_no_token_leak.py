# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property tests: connect_git_host never leaks OAuth tokens.

Property 2: For any response returned by connect_git_host, the serialized
response does not contain any string matching an OAuth access token pattern.

Validates: Requirement 5.2
"""

import asyncio
import json
import re
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

import container.code_mcp_server as server  # noqa: E402

# Patterns that look like OAuth tokens (GitHub PATs, generic bearer tokens)
TOKEN_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"gho_[A-Za-z0-9]{36}"),
    re.compile(r"ghu_[A-Za-z0-9]{36}"),
    re.compile(r"ghs_[A-Za-z0-9]{36}"),
    re.compile(r"ghr_[A-Za-z0-9]{36}"),
    re.compile(r"ya29\.[A-Za-z0-9_-]{20,}"),
    re.compile(r"eyJ[A-Za-z0-9_-]{50,}"),  # JWT-like
]

git_host_domains = st.from_regex(r"[a-z][a-z0-9\-]{0,20}\.[a-z]{2,6}", fullmatch=True)

# Fake tokens that should never appear in output
FAKE_TOKENS = [
    "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh",
    "gho_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh",
    "ya29.a0ARrdaM_fake_token_value_here",
]


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _assert_no_tokens(result):
    serialized = json.dumps(result)
    for pattern in TOKEN_PATTERNS:
        assert not pattern.search(serialized), f"Token pattern {pattern.pattern} found in response"
    for token in FAKE_TOKENS:
        assert token not in serialized, f"Fake token leaked in response"


class TestConnectGitHostNoTokenLeak:

    @given(host=git_host_domains)
    @settings(max_examples=20)
    def test_already_connected_no_leak(self, host):
        """Token returned by SDK must not appear in tool response."""
        for fake_token in FAKE_TOKENS:
            with patch.object(server, "_get_credential", return_value=(fake_token, None)):
                result = _run(server.connect_git_host(host, _user_id="u1", ctx=None))
            _assert_no_tokens(result)

    @given(host=git_host_domains)
    @settings(max_examples=20)
    def test_connected_after_elicit_no_leak(self, host):
        """After elicitation, token must not appear in response."""
        for fake_token in FAKE_TOKENS:
            call_count = 0

            def _mock(uid, gh):
                nonlocal call_count
                call_count += 1
                return (None, "https://auth.example.com") if call_count == 1 else (fake_token, None)

            ctx = MagicMock()
            ctx.elicit = AsyncMock(return_value=MagicMock(action="accept"))
            with patch.object(server, "_get_credential", side_effect=_mock):
                call_count = 0
                result = _run(server.connect_git_host(host, _user_id="u1", ctx=ctx))
            _assert_no_tokens(result)

    @given(host=git_host_domains)
    @settings(max_examples=20)
    def test_failed_response_no_leak(self, host):
        """Failed responses must not leak tokens either."""
        with patch.object(server, "_get_credential", side_effect=Exception("ServiceError")):
            result = _run(server.connect_git_host(host, _user_id="u1", ctx=None))
        _assert_no_tokens(result)
