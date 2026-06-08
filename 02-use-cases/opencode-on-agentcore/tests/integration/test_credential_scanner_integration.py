# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Integration test: credential scanner pattern parity.

Tests with files containing each credential pattern type (AWS keys,
sk- keys, PEM, high-entropy) and verifies all patterns replaced with
``<REDACTED_SECRET>``.

Requirements: 21.1, 21.2, 21.3, 21.4, 21.5
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stub strands before importing
# ---------------------------------------------------------------------------
strands_mock = MagicMock()
strands_mock.tool = lambda fn: fn
sys.modules.setdefault("strands", strands_mock)

from container.tools.scan_and_strip_credentials import (  # noqa: E402
    scan_and_strip_content,
    PLACEHOLDER,
)

import pytest  # noqa: E402


class TestCredentialScannerIntegration:
    """Test each credential pattern type is detected and replaced."""

    def test_aws_access_key_detected(self):
        """Verify AWS access key pattern AKIA... is replaced (Req 21.1)."""
        content = 'aws_key = "AKIAIOSFODNN7EXAMPLE"'
        cleaned, findings = scan_and_strip_content(content)

        assert PLACEHOLDER in cleaned
        assert "AKIAIOSFODNN7EXAMPLE" not in cleaned
        assert len(findings) >= 1
        assert any(f["pattern"] == "AWS Access Key" for f in findings)

    def test_sk_api_key_detected(self):
        """Verify sk- API key pattern is replaced (Req 21.2)."""
        content = 'api_key = "sk-abcdefghijklmnopqrstuvwxyz1234"'
        cleaned, findings = scan_and_strip_content(content)

        assert PLACEHOLDER in cleaned
        assert "sk-abcdefghijklmnopqrstuvwxyz1234" not in cleaned
        assert len(findings) >= 1
        assert any(f["pattern"] == "API Key (sk-)" for f in findings)

    def test_pem_private_key_detected(self):
        """Verify PEM private key header is replaced (Req 21.3)."""
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQ..."
        cleaned, findings = scan_and_strip_content(content)

        assert PLACEHOLDER in cleaned
        assert "-----BEGIN RSA PRIVATE KEY-----" not in cleaned
        assert len(findings) >= 1
        assert any(f["pattern"] == "PEM Private Key" for f in findings)

    def test_high_entropy_secret_detected(self):
        """Verify high-entropy secret assignment is replaced (Req 21.4)."""
        content = 'secret = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"'
        cleaned, findings = scan_and_strip_content(content)

        assert PLACEHOLDER in cleaned
        assert len(findings) >= 1
        assert any(f["pattern"] == "High-entropy assignment" for f in findings)

    def test_pem_ec_private_key_detected(self):
        """Verify EC PEM private key header is replaced (Req 21.3)."""
        content = "-----BEGIN EC PRIVATE KEY-----\nMHQCAQEE..."
        cleaned, findings = scan_and_strip_content(content)

        assert PLACEHOLDER in cleaned
        assert "-----BEGIN EC PRIVATE KEY-----" not in cleaned

    def test_multiple_patterns_in_one_file(self):
        """Verify multiple credential types in one file all replaced (Req 21.5)."""
        content = (
            'aws_key = "AKIAIOSFODNN7EXAMPLE"\n'
            'openai_key = "sk-abcdefghijklmnopqrstuvwxyz1234"\n'
            "-----BEGIN RSA PRIVATE KEY-----\n"
            'password = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"\n'
        )
        cleaned, findings = scan_and_strip_content(content)

        assert "AKIAIOSFODNN7EXAMPLE" not in cleaned
        assert "sk-abcdefghijklmnopqrstuvwxyz1234" not in cleaned
        assert "-----BEGIN RSA PRIVATE KEY-----" not in cleaned
        # All replaced with placeholder
        assert cleaned.count(PLACEHOLDER) >= 4
        assert len(findings) >= 4

    def test_clean_content_unchanged(self):
        """Verify content without credentials is not modified (Req 21.5)."""
        content = 'print("Hello, world!")\nx = 42\n'
        cleaned, findings = scan_and_strip_content(content)

        assert cleaned == content
        assert len(findings) == 0

    def test_password_assignment_with_colon(self):
        """Verify password: 'value' pattern detected (Req 21.4)."""
        content = "password: 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij'"
        cleaned, findings = scan_and_strip_content(content)

        assert PLACEHOLDER in cleaned
        assert len(findings) >= 1

    def test_token_assignment_detected(self):
        """Verify token = 'value' pattern detected (Req 21.4)."""
        content = 'token = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"'
        cleaned, findings = scan_and_strip_content(content)

        assert PLACEHOLDER in cleaned
        assert len(findings) >= 1
