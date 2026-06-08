# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the inline OAuth callback authorizer Lambda.

Extracts the handler from AUTHORIZER_LAMBDA_CODE via exec and exercises
it directly — no API Gateway involved.

Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 3.1, 3.2, 5.1, 5.2
"""

import json

import pytest

from stacks.callback_api_stack import AUTHORIZER_LAMBDA_CODE

# ---------------------------------------------------------------------------
# Extract the handler function from the inline code string
# ---------------------------------------------------------------------------
_ns: dict = {}
exec(AUTHORIZER_LAMBDA_CODE, _ns)
handler = _ns["handler"]


def _event(session_id=None, state=None):
    """Build a minimal API Gateway v2 authorizer request event."""
    params = {}
    if session_id is not None:
        params["session_id"] = session_id
    if state is not None:
        params["state"] = state
    return {"queryStringParameters": params if params else None}


# ---------------------------------------------------------------------------
# Missing parameters (Req 3.2)
# ---------------------------------------------------------------------------

class TestMissingParams:
    def test_missing_session_id(self):
        event = _event(state=json.dumps({"user_id": "u1"}))
        assert handler(event, None) == {"isAuthorized": False}

    def test_missing_state(self):
        event = _event(session_id="a" * 10)
        assert handler(event, None) == {"isAuthorized": False}

    def test_missing_both(self):
        event = _event()
        assert handler(event, None) == {"isAuthorized": False}

    def test_empty_query_string_parameters(self):
        event = {"queryStringParameters": None}
        assert handler(event, None) == {"isAuthorized": False}


# ---------------------------------------------------------------------------
# session_id format validation (Req 1.1, 1.2)
# ---------------------------------------------------------------------------

class TestSessionIdValidation:
    def test_too_short(self):
        event = _event(session_id="abc", state=json.dumps({"user_id": "u1"}))
        assert handler(event, None) == {"isAuthorized": False}

    def test_exactly_nine_chars_rejected(self):
        event = _event(session_id="a" * 9, state=json.dumps({"user_id": "u1"}))
        assert handler(event, None) == {"isAuthorized": False}

    def test_invalid_chars_space(self):
        event = _event(session_id="abc def ghij", state=json.dumps({"user_id": "u1"}))
        assert handler(event, None) == {"isAuthorized": False}

    def test_invalid_chars_angle_brackets(self):
        event = _event(session_id="<script>alert</script>", state=json.dumps({"user_id": "u1"}))
        assert handler(event, None) == {"isAuthorized": False}

    def test_exactly_ten_chars_accepted(self):
        event = _event(session_id="a" * 10, state=json.dumps({"user_id": "u1"}))
        assert handler(event, None) == {"isAuthorized": True}


# ---------------------------------------------------------------------------
# state JSON validation (Req 2.1, 2.2, 2.3)
# ---------------------------------------------------------------------------

class TestStateValidation:
    def test_not_valid_json(self):
        event = _event(session_id="a" * 10, state="not-json")
        assert handler(event, None) == {"isAuthorized": False}

    def test_json_array(self):
        event = _event(session_id="a" * 10, state=json.dumps([1, 2, 3]))
        assert handler(event, None) == {"isAuthorized": False}

    def test_json_string(self):
        event = _event(session_id="a" * 10, state=json.dumps("just a string"))
        assert handler(event, None) == {"isAuthorized": False}

    def test_json_dict_without_user_id(self):
        event = _event(session_id="a" * 10, state=json.dumps({"foo": "bar"}))
        assert handler(event, None) == {"isAuthorized": False}


# ---------------------------------------------------------------------------
# Happy path (Req 3.1)
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_valid_request(self):
        event = _event(
            session_id="session-id_12345",
            state=json.dumps({"user_id": "user-abc-123"}),
        )
        assert handler(event, None) == {"isAuthorized": True}

    def test_session_id_with_allowed_special_chars(self):
        """Slashes, colons, dots, underscores, hyphens are all allowed."""
        event = _event(
            session_id="us-east-1:abc/def_ghi.jkl",
            state=json.dumps({"user_id": "u1"}),
        )
        assert handler(event, None) == {"isAuthorized": True}

    def test_state_with_extra_fields(self):
        """Extra fields in state dict are fine — only user_id is required."""
        event = _event(
            session_id="a" * 10,
            state=json.dumps({"user_id": "u1", "redirect": "/home"}),
        )
        assert handler(event, None) == {"isAuthorized": True}
