# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property test: JWT extraction or rejection in the Gateway interceptor.

**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

Property 6 -- JWT extraction or rejection:
  For any HTTP request to the interceptor, if the Authorization header
  contains a valid decodable JWT with a `sub` or `email` claim, the
  interceptor SHALL extract it as `_user_id`. For any request where the
  Authorization header is missing, empty, or contains a malformed JWT
  (bad base64, invalid JSON, missing claims), the interceptor SHALL
  return an error response and SHALL NOT set `_user_id` to "anonymous".
"""

from __future__ import annotations

import base64
import importlib
import json

from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Import the interceptor handler via importlib because "lambda" is a
# Python keyword and cannot be used in a normal import statement.
# ---------------------------------------------------------------------------
_interceptor_module = importlib.import_module("lambda.interceptor.index")
handler = _interceptor_module.handler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jwt_token(claims: dict) -> str:
    """Build a minimal unsigned JWT (header.payload.signature) from claims."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.fakesig"


def _make_event(auth_header: str | None) -> dict:
    """Build a minimal interceptor event with an optional Authorization header."""
    headers: dict = {}
    if auth_header is not None:
        headers["Authorization"] = auth_header
    return {
        "mcp": {
            "gatewayRequest": {
                "headers": headers,
                "body": {
                    "method": "tools/call",
                    "params": {"name": "test_tool", "arguments": {}},
                },
            }
        }
    }


def _is_error_response(result: dict) -> bool:
    """Check if the interceptor returned a 401 error response."""
    return result.get("statusCode") == 401


def _get_injected_user_id(result: dict) -> str | None:
    """Extract the _user_id injected into tool call arguments, if any."""
    try:
        return (
            result["mcp"]["transformedGatewayRequest"]["body"]
            ["params"]["arguments"].get("_user_id")
        )
    except (KeyError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Identifiers for sub/email claims
_identifier = st.text(
    alphabet=st.sampled_from(
        list("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_@.")
    ),
    min_size=1,
    max_size=64,
)

# Valid claims: at least one of sub or email is present and non-empty
_valid_claims = st.one_of(
    # Both sub and email
    st.fixed_dictionaries({"sub": _identifier, "email": _identifier}),
    # Only sub
    st.fixed_dictionaries({"sub": _identifier}),
    # Only email
    st.fixed_dictionaries({"email": _identifier}),
)

# Malformed JWT strings that should cause decode failures
_malformed_jwt = st.one_of(
    # Not enough dots (no payload segment)
    st.just("Bearer header_only"),
    # Bad base64 in payload segment
    st.text(min_size=1, max_size=20).map(lambda s: f"Bearer aaa.!!!{s}!!!.sig"),
    # Valid base64 but not valid JSON
    st.just("Bearer aaa." + base64.urlsafe_b64encode(b"not json").rstrip(b"=").decode() + ".sig"),
    # Empty payload segment
    st.just("Bearer aaa..sig"),
)

# Missing claims: valid JWT structure but no sub or email
_missing_claims = st.fixed_dictionaries({
    "aud": st.just("some-audience"),
    "iss": st.just("some-issuer"),
}).map(lambda claims: "Bearer " + _make_jwt_token(claims))

# Missing or empty Authorization header
_missing_auth = st.one_of(
    st.just(None),       # No header at all
    st.just(""),         # Empty string
    st.just("Basic abc123"),  # Wrong scheme
    st.just("token xyz"),     # No Bearer prefix
)


# ---------------------------------------------------------------------------
# Property 6: JWT extraction or rejection
# ---------------------------------------------------------------------------


class TestInterceptorJwt:
    """**Validates: Requirements 4.1, 4.2, 4.3, 4.4**"""

    @given(claims=_valid_claims)
    @settings(max_examples=100, deadline=5_000)
    def test_valid_jwt_extracts_user_id(self, claims: dict):
        """For any valid JWT with sub or email, the interceptor SHALL extract
        the claim as _user_id and return a transformed request (not an error).

        **Validates: Requirements 4.1**
        """
        token = _make_jwt_token(claims)
        event = _make_event(f"Bearer {token}")
        result = handler(event, None)

        # Should NOT be an error response
        assert not _is_error_response(result), (
            f"Valid JWT with claims {claims} returned error: {result}"
        )

        # Should have extracted user_id
        user_id = _get_injected_user_id(result)
        expected = claims.get("sub") or claims.get("email")
        assert user_id == expected, (
            f"Expected user_id={expected!r}, got {user_id!r} for claims {claims}"
        )

        # user_id should NEVER be "anonymous"
        assert user_id != "anonymous", (
            f"user_id is 'anonymous' for valid JWT with claims {claims}"
        )

    @given(auth_header=_malformed_jwt)
    @settings(max_examples=100, deadline=5_000)
    def test_malformed_jwt_returns_error(self, auth_header: str):
        """For any malformed JWT (bad base64, invalid JSON), the interceptor
        SHALL return an error response.

        **Validates: Requirements 4.2**
        """
        event = _make_event(auth_header)
        result = handler(event, None)

        assert _is_error_response(result), (
            f"Malformed JWT '{auth_header}' did not return error: {result}"
        )

        # Should NOT contain "anonymous" anywhere in the response
        result_str = json.dumps(result)
        assert "anonymous" not in result_str, (
            f"Response contains 'anonymous' for malformed JWT: {result}"
        )

    @given(auth_header=_missing_claims)
    @settings(max_examples=100, deadline=5_000)
    def test_missing_claims_returns_error(self, auth_header: str):
        """For any JWT missing both sub and email claims, the interceptor
        SHALL return an error response.

        **Validates: Requirements 4.3**
        """
        event = _make_event(auth_header)
        result = handler(event, None)

        assert _is_error_response(result), (
            f"JWT with missing claims did not return error: {result}"
        )

        # Should NOT contain "anonymous" anywhere
        result_str = json.dumps(result)
        assert "anonymous" not in result_str, (
            f"Response contains 'anonymous' for missing-claims JWT: {result}"
        )

    @given(auth_value=_missing_auth)
    @settings(max_examples=100, deadline=5_000)
    def test_missing_or_invalid_auth_header_returns_error(self, auth_value):
        """For any missing, empty, or non-Bearer Authorization header, the
        interceptor SHALL return an error response.

        **Validates: Requirements 4.4**
        """
        event = _make_event(auth_value)
        result = handler(event, None)

        assert _is_error_response(result), (
            f"Missing/invalid auth '{auth_value}' did not return error: {result}"
        )

        # Should NOT contain "anonymous" anywhere
        result_str = json.dumps(result)
        assert "anonymous" not in result_str, (
            f"Response contains 'anonymous' for missing auth: {result}"
        )
