# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property tests: connect_git_host response schema invariant.

Property 1: For any git_host domain and any mocked Identity SDK response,
the result contains `status` in {connected, already_connected, failed},
`git_host` matching input, non-empty `message`, and `error` when status=failed.

Validates: Requirements 3.1, 3.2, 3.3, 3.4
"""

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import container.code_mcp_server as server  # noqa: E402

VALID_STATUSES = {"connected", "already_connected", "failed", "action_required"}

git_host_domains = st.from_regex(r"[a-z][a-z0-9\-]{0,20}\.[a-z]{2,6}", fullmatch=True)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _validate_response(result, git_host):
    assert result["status"] in VALID_STATUSES
    assert result["git_host"] == git_host
    assert isinstance(result["message"], str) and len(result["message"]) > 0
    if result["status"] == "failed":
        assert "error" in result and len(result["error"]) > 0
    if result["status"] == "action_required":
        assert "authorization_url" in result


class TestConnectGitHostResponseSchema:

    @given(host=git_host_domains)
    @settings(max_examples=30)
    def test_already_connected_response(self, host):
        """When Identity SDK returns a token, status is already_connected."""
        with patch.object(server, "_get_credential", return_value=("tok", None)):
            result = _run(server.connect_git_host(host, _user_id="u1", ctx=None))
        _validate_response(result, host)
        assert result["status"] == "already_connected"

    @given(host=git_host_domains)
    @settings(max_examples=30)
    def test_connected_after_elicitation(self, host):
        """When elicitation succeeds and token appears, status is connected."""
        call_count = 0

        def _mock_cred(uid, gh):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return None, "https://auth.example.com"
            return ("tok", None)

        ctx = MagicMock()
        ctx.elicit = AsyncMock(return_value=MagicMock(action="accept"))

        with patch.object(server, "_get_credential", side_effect=_mock_cred):
            call_count = 0
            result = _run(server.connect_git_host(host, _user_id="u1", ctx=ctx))
        _validate_response(result, host)
        assert result["status"] == "connected"

    @given(host=git_host_domains)
    @settings(max_examples=30)
    def test_failed_no_provider(self, host):
        """When no credential provider exists, status is failed."""
        with patch.object(server, "_get_credential", side_effect=Exception("NoCredentialProvider")):
            result = _run(server.connect_git_host(host, _user_id="u1", ctx=None))
        _validate_response(result, host)
        assert result["status"] == "failed"

    @given(host=git_host_domains)
    @settings(max_examples=30)
    def test_action_required_user_cancel(self, host):
        """When user cancels elicitation, status is action_required with auth URL."""
        ctx = MagicMock()
        ctx.elicit = AsyncMock(return_value=MagicMock(action="cancel"))

        with patch.object(server, "_get_credential", return_value=(None, "https://auth.example.com")):
            result = _run(server.connect_git_host(host, _user_id="u1", ctx=ctx))
        assert result["status"] == "action_required"
        assert result["git_host"] == host
        assert "authorization_url" in result
        assert result["authorization_url"] == "https://auth.example.com"
        assert isinstance(result["message"], str) and len(result["message"]) > 0

    def test_failed_no_user_id(self):
        result = _run(server.connect_git_host("github.com", _user_id="", ctx=None))
        _validate_response(result, "github.com")
        assert result["status"] == "failed"

    @given(host=git_host_domains)
    @settings(max_examples=30)
    def test_failed_sdk_error(self, host):
        """When Identity SDK raises a generic error, status is failed."""
        with patch.object(server, "_get_credential", side_effect=Exception("ServiceUnavailable")):
            result = _run(server.connect_git_host(host, _user_id="u1", ctx=None))
        _validate_response(result, host)
        assert result["status"] == "failed"
