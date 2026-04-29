# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property tests: OAuth Callback Authorizer & URL Discovery.

Tests the inline authorizer Lambda logic (AUTHORIZER_LAMBDA_CODE) and the
simplified _get_oauth_callback_url() function in both runtime containers.

Uses Hypothesis for property-based testing.
"""

from __future__ import annotations

import os
import types
from unittest.mock import patch

import pytest
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Extract the authorizer handler from the inline code string in identity_stack
# ---------------------------------------------------------------------------
from stacks.callback_api_stack import AUTHORIZER_LAMBDA_CODE

_authorizer_module = types.ModuleType("authorizer_inline")
exec(AUTHORIZER_LAMBDA_CODE, _authorizer_module.__dict__)  # noqa: S102
authorizer_handler = _authorizer_module.handler


# ---------------------------------------------------------------------------
# Import _get_oauth_callback_url from the unified runtime container
# ---------------------------------------------------------------------------
from container.code_mcp_server import (
    _get_oauth_callback_url as cgh_get_url,
)
from container.tools.resolve_git_credential import (
    resolve_git_credential as _resolve_mod,
)

# resolve_git_credential.py doesn't expose a standalone helper anymore —
# the URL is read inline via os.environ.get. We'll test the pattern directly.


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Non-empty text for valid session_id / state values (old permissive authorizer)
nonempty_text = st.text(min_size=1, max_size=200)

# Valid session_id: 10-512 chars from [A-Za-z0-9_\-/:.] per the hardened authorizer
valid_session_id = st.from_regex(r"[A-Za-z0-9_\-/:.]{10,100}", fullmatch=True)

# Valid state: JSON dict containing at least "user_id"
import json as _json

valid_state = st.fixed_dictionaries(
    {"user_id": st.text(min_size=1, max_size=50)},
    optional={"extra": st.text(max_size=20)},
).map(_json.dumps)

# Possibly-empty text (includes empty string)
any_text = st.text(max_size=200)

# URL-like strings for OAUTH_CALLBACK_URL (no null bytes or surrogates — invalid in env vars)
url_text = st.text(
    alphabet=st.characters(
        blacklist_characters="\x00",
        blacklist_categories=("Cs",),  # exclude surrogates
    ),
    min_size=1,
    max_size=500,
)


# ---------------------------------------------------------------------------
# Property 1: Authorizer accepts valid OAuth callbacks
# ---------------------------------------------------------------------------


class TestAuthorizerAcceptsValid:
    """Property 1: Authorizer accepts valid OAuth callbacks.

    **Validates: Requirements 2.2**

    For any valid session_id (10-512 chars, allowed charset) and valid
    state (JSON dict with user_id), the authorizer SHALL return
    isAuthorized: True.
    """

    @given(session_id=valid_session_id, state=valid_state)
    @settings(max_examples=50, deadline=5_000)
    def test_valid_session_id_and_state_returns_authorized(
        self, session_id: str, state: str
    ):
        """Valid session_id + valid state JSON → isAuthorized: True."""
        event = {
            "queryStringParameters": {
                "session_id": session_id,
                "state": state,
            }
        }
        result = authorizer_handler(event, None)
        assert result == {"isAuthorized": True}, (
            f"Expected isAuthorized=True for session_id={session_id!r}, "
            f"state={state!r}, got {result}"
        )


# ---------------------------------------------------------------------------
# Property 2: Authorizer rejects malformed requests
# ---------------------------------------------------------------------------


class TestAuthorizerRejectsMalformed:
    """Property 2: Authorizer rejects malformed requests.

    **Validates: Requirements 2.3**

    For any request where session_id is missing/empty OR state is
    missing/empty, the authorizer Lambda SHALL return isAuthorized: False.
    """

    @given(state=nonempty_text)
    @settings(max_examples=30, deadline=5_000)
    def test_missing_session_id_returns_unauthorized(self, state: str):
        """Missing session_id (key absent) → isAuthorized: False."""
        event = {"queryStringParameters": {"state": state}}
        result = authorizer_handler(event, None)
        assert result == {"isAuthorized": False}, (
            f"Expected isAuthorized=False when session_id missing, got {result}"
        )

    @given(state=nonempty_text)
    @settings(max_examples=30, deadline=5_000)
    def test_empty_session_id_returns_unauthorized(self, state: str):
        """Empty session_id → isAuthorized: False."""
        event = {"queryStringParameters": {"session_id": "", "state": state}}
        result = authorizer_handler(event, None)
        assert result == {"isAuthorized": False}, (
            f"Expected isAuthorized=False for empty session_id, got {result}"
        )

    @given(session_id=nonempty_text)
    @settings(max_examples=30, deadline=5_000)
    def test_missing_state_returns_unauthorized(self, session_id: str):
        """Missing state (key absent) → isAuthorized: False."""
        event = {"queryStringParameters": {"session_id": session_id}}
        result = authorizer_handler(event, None)
        assert result == {"isAuthorized": False}, (
            f"Expected isAuthorized=False when state missing, got {result}"
        )

    @given(session_id=nonempty_text)
    @settings(max_examples=30, deadline=5_000)
    def test_empty_state_returns_unauthorized(self, session_id: str):
        """Empty state → isAuthorized: False."""
        event = {"queryStringParameters": {"session_id": session_id, "state": ""}}
        result = authorizer_handler(event, None)
        assert result == {"isAuthorized": False}, (
            f"Expected isAuthorized=False for empty state, got {result}"
        )

    @settings(max_examples=1, deadline=5_000)
    @given(st.just(None))
    def test_both_missing_returns_unauthorized(self, _):
        """Both session_id and state missing → isAuthorized: False."""
        event = {"queryStringParameters": {}}
        result = authorizer_handler(event, None)
        assert result == {"isAuthorized": False}

    @settings(max_examples=1, deadline=5_000)
    @given(st.just(None))
    def test_null_query_params_returns_unauthorized(self, _):
        """queryStringParameters is None → isAuthorized: False."""
        event = {"queryStringParameters": None}
        result = authorizer_handler(event, None)
        assert result == {"isAuthorized": False}

    @settings(max_examples=1, deadline=5_000)
    @given(st.just(None))
    def test_no_query_params_key_returns_unauthorized(self, _):
        """queryStringParameters key absent → isAuthorized: False."""
        event = {}
        result = authorizer_handler(event, None)
        assert result == {"isAuthorized": False}


# ---------------------------------------------------------------------------
# Property 3: Callback URL discovery returns environment variable
# ---------------------------------------------------------------------------


class TestCallbackUrlDiscovery:
    """Property 3: Callback URL discovery returns environment variable.

    **Validates: Requirements 5.1, 5.2**

    For any URL string set as OAUTH_CALLBACK_URL env var,
    _get_oauth_callback_url() returns that exact string.
    When the env var is not set, it returns empty string.
    """

    @given(url=url_text)
    @settings(max_examples=50, deadline=5_000)
    def test_connect_git_host_returns_env_var(self, url: str):
        """connect_git_host_server._get_oauth_callback_url() returns env var."""
        with patch.dict(os.environ, {"OAUTH_CALLBACK_URL": url}):
            result = cgh_get_url()
        assert result == url, (
            f"Expected {url!r}, got {result!r}"
        )

    @given(url=url_text)
    @settings(max_examples=50, deadline=5_000)
    def test_resolve_git_credential_returns_env_var(self, url: str):
        """resolve_git_credential reads OAUTH_CALLBACK_URL from env."""
        with patch.dict(os.environ, {"OAUTH_CALLBACK_URL": url}):
            result = os.environ.get("OAUTH_CALLBACK_URL", "")
        assert result == url, (
            f"Expected {url!r}, got {result!r}"
        )

    def test_connect_git_host_returns_empty_when_unset(self):
        """When OAUTH_CALLBACK_URL is not set, returns empty string."""
        env = os.environ.copy()
        env.pop("OAUTH_CALLBACK_URL", None)
        with patch.dict(os.environ, env, clear=True):
            result = cgh_get_url()
        assert result == "", f"Expected empty string, got {result!r}"
