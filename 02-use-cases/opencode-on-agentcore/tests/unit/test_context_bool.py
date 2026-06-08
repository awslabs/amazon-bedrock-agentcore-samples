# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the context_bool helper (stacks/__init__.py).

Validates: Requirement 2.3
"""

import aws_cdk as cdk
import pytest

from stacks import context_bool


def _make_scope(context: dict | None = None) -> cdk.App:
    """Create a minimal CDK App with the given context."""
    return cdk.App(context=context or {})


class TestContextBoolWithBooleans:
    """context_bool returns the bool value directly for native booleans."""

    def test_true_returns_true(self):
        app = _make_scope({"flag": True})
        assert context_bool(app, "flag") is True

    def test_false_returns_false(self):
        app = _make_scope({"flag": False})
        assert context_bool(app, "flag") is False


class TestContextBoolWithTruthyStrings:
    """context_bool returns True for truthy string variants."""

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "1", "yes", "on"])
    def test_truthy_strings(self, value: str):
        app = _make_scope({"flag": value})
        assert context_bool(app, "flag") is True

    def test_truthy_string_with_whitespace(self):
        app = _make_scope({"flag": "  true  "})
        assert context_bool(app, "flag") is True


class TestContextBoolWithFalsyStrings:
    """context_bool returns False for falsy string variants."""

    @pytest.mark.parametrize("value", ["false", "0", "no", "off"])
    def test_falsy_strings(self, value: str):
        app = _make_scope({"flag": value})
        assert context_bool(app, "flag") is False

    def test_empty_string_returns_false(self):
        app = _make_scope({"flag": ""})
        assert context_bool(app, "flag") is False


class TestContextBoolWithNoneAndMissing:
    """context_bool returns the default for None and missing keys."""

    def test_none_returns_default_false(self):
        app = _make_scope({"flag": None})
        assert context_bool(app, "flag") is False

    def test_none_returns_custom_default_true(self):
        app = _make_scope({"flag": None})
        assert context_bool(app, "flag", default=True) is True

    def test_missing_key_returns_default_false(self):
        app = _make_scope({})
        assert context_bool(app, "flag") is False

    def test_missing_key_returns_custom_default_true(self):
        app = _make_scope({})
        assert context_bool(app, "flag", default=True) is True
