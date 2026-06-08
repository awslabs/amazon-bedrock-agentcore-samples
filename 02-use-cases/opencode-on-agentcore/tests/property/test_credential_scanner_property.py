# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property test: Credential scanner detection and replacement.

**Validates: Requirements 9.4, 21.1, 21.2, 21.3, 21.4, 21.5**

Property 8 — Credential scanner detection and replacement:
  For any file content containing credential patterns, verify all patterns
  replaced with `<REDACTED_SECRET>`. For content without patterns, verify
  output equals input.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from container.tools.scan_and_strip_credentials import (
    PATTERNS,
    PLACEHOLDER,
    scan_and_strip_content,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Safe alphabet that won't accidentally form credential patterns
_SAFE_ALPHABET = st.sampled_from(
    list("abcdefghijlmnopqrtuvwxyz .,:;!?\n\t(){}[]0123456789+-*/")
)
_safe_text = st.text(alphabet=_SAFE_ALPHABET, min_size=0, max_size=80)

# AWS access key: AKIA + exactly 16 uppercase alphanumeric chars
_aws_key = st.from_regex(r"AKIA[0-9A-Z]{16}", fullmatch=True)

# sk- API key: sk- + 20-40 alphanumeric chars
_sk_key = st.from_regex(r"sk-[a-zA-Z0-9]{20,40}", fullmatch=True)

# PEM private key headers
_pem_header = st.sampled_from([
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN EC PRIVATE KEY-----",
    "-----BEGIN DSA PRIVATE KEY-----",
])

# High-entropy secret assignment: keyword = "base64-ish value of 20+ chars"
_high_entropy_keyword = st.sampled_from(["secret", "password", "token", "key",
                                          "SECRET", "Password", "TOKEN", "Key"])
_high_entropy_value = st.from_regex(r"[A-Za-z0-9+/=]{20,40}", fullmatch=True)
_assignment_op = st.sampled_from(["=", ":"])
_quote = st.sampled_from(['"', "'"])


@st.composite
def _high_entropy_assignment(draw):
    kw = draw(_high_entropy_keyword)
    op = draw(_assignment_op)
    q = draw(_quote)
    val = draw(_high_entropy_value)
    spacing = draw(st.sampled_from([" ", "  ", ""]))
    return f"{kw}{spacing}{op}{spacing}{q}{val}{q}"


_high_entropy = _high_entropy_assignment()


def _has_any_pattern(content: str) -> bool:
    """Return True if content matches any credential pattern."""
    return any(regex.search(content) for _, regex in PATTERNS)


# ---------------------------------------------------------------------------
# Property 8a: AWS access key detection and replacement
# ---------------------------------------------------------------------------


class TestAWSAccessKeyProperty:
    """**Validates: Requirements 21.1**"""

    @given(prefix=_safe_text, key=_aws_key, suffix=_safe_text)
    @settings(max_examples=100, deadline=5_000)
    def test_aws_key_replaced_with_placeholder(self, prefix, key, suffix):
        """Any embedded AWS access key (AKIA + 16 uppercase alphanum) is replaced."""
        content = f"{prefix}{key}{suffix}"
        cleaned, findings = scan_and_strip_content(content)

        assert PLACEHOLDER in cleaned
        assert key not in cleaned
        assert any(f["pattern"] == "AWS Access Key" for f in findings)


# ---------------------------------------------------------------------------
# Property 8b: sk- API key detection and replacement
# ---------------------------------------------------------------------------


class TestSkApiKeyProperty:
    """**Validates: Requirements 21.2**"""

    @given(prefix=_safe_text, key=_sk_key, suffix=_safe_text)
    @settings(max_examples=100, deadline=5_000)
    def test_sk_key_replaced_with_placeholder(self, prefix, key, suffix):
        """Any embedded sk- API key (sk- + 20+ alphanum) is replaced."""
        content = f"{prefix}{key}{suffix}"
        cleaned, findings = scan_and_strip_content(content)

        assert PLACEHOLDER in cleaned
        assert key not in cleaned
        assert any(f["pattern"] == "API Key (sk-)" for f in findings)


# ---------------------------------------------------------------------------
# Property 8c: PEM private key header detection and replacement
# ---------------------------------------------------------------------------


class TestPemPrivateKeyProperty:
    """**Validates: Requirements 21.3**"""

    @given(prefix=_safe_text, header=_pem_header, suffix=_safe_text)
    @settings(max_examples=100, deadline=5_000)
    def test_pem_header_replaced_with_placeholder(self, prefix, header, suffix):
        """Any PEM private key header is replaced."""
        content = f"{prefix}{header}{suffix}"
        cleaned, findings = scan_and_strip_content(content)

        assert PLACEHOLDER in cleaned
        assert header not in cleaned
        assert any(f["pattern"] == "PEM Private Key" for f in findings)


# ---------------------------------------------------------------------------
# Property 8d: High-entropy secret assignment detection and replacement
# ---------------------------------------------------------------------------


class TestHighEntropyAssignmentProperty:
    """**Validates: Requirements 21.4**"""

    @given(prefix=_safe_text, assignment=_high_entropy, suffix=_safe_text)
    @settings(max_examples=100, deadline=5_000)
    def test_high_entropy_assignment_replaced(self, prefix, assignment, suffix):
        """Any high-entropy secret assignment is replaced."""
        content = f"{prefix}{assignment}{suffix}"
        cleaned, findings = scan_and_strip_content(content)

        assert PLACEHOLDER in cleaned
        assert any(f["pattern"] == "High-entropy assignment" for f in findings)


# ---------------------------------------------------------------------------
# Property 8e: Clean content passes through unchanged
# ---------------------------------------------------------------------------


class TestCleanContentProperty:
    """**Validates: Requirements 9.4**"""

    @given(content=_safe_text)
    @settings(max_examples=100, deadline=5_000)
    def test_no_credential_content_unchanged(self, content):
        """Content without any credential patterns passes through unchanged."""
        # Skip if the safe text accidentally matches a pattern
        if _has_any_pattern(content):
            return

        cleaned, findings = scan_and_strip_content(content)

        assert cleaned == content
        assert findings == []


# ---------------------------------------------------------------------------
# New strategies for expanded patterns (Req 12)
# ---------------------------------------------------------------------------

# AWS temporary credentials: ASIA + exactly 16 uppercase alphanumeric chars
_aws_temp_key = st.from_regex(r"ASIA[0-9A-Z]{16}", fullmatch=True)

# GitHub tokens: gh[pousr]_ + 36-80 alphanumeric/underscore chars
_gh_prefix = st.sampled_from(["ghp_", "gho_", "ghu_", "ghs_", "ghr_"])
_gh_suffix = st.from_regex(r"[A-Za-z0-9_]{36,80}", fullmatch=True)


@st.composite
def _github_token(draw):
    prefix = draw(_gh_prefix)
    suffix = draw(_gh_suffix)
    return f"{prefix}{suffix}"


# GitHub PAT (legacy): github_pat_ + 22-80 alphanumeric/underscore chars
_github_pat_legacy = st.builds(
    lambda s: f"github_pat_{s}",
    st.from_regex(r"[A-Za-z0-9_]{22,80}", fullmatch=True),
)


# ---------------------------------------------------------------------------
# Property 9: Credential scanner detects all known patterns
# ---------------------------------------------------------------------------


class TestAllPatternsDetectedProperty:
    """**Validates: Requirements 12.1, 12.2, 12.3, 12.4, 12.5**

    Property 9: For any credential matching any defined pattern,
    scan_and_strip_content SHALL replace it with REDACTED_SECRET.
    """

    @given(prefix=_safe_text, key=_aws_key, suffix=_safe_text)
    @settings(max_examples=100, deadline=5_000)
    def test_akia_key_redacted(self, prefix, key, suffix):
        """AKIA AWS access keys are redacted."""
        content = f"{prefix}{key}{suffix}"
        cleaned, findings = scan_and_strip_content(content)
        assert key not in cleaned
        assert PLACEHOLDER in cleaned

    @given(prefix=_safe_text, key=_aws_temp_key, suffix=_safe_text)
    @settings(max_examples=100, deadline=5_000)
    def test_asia_temp_key_redacted(self, prefix, key, suffix):
        """ASIA temporary AWS credentials are redacted."""
        content = f"{prefix}{key}{suffix}"
        cleaned, findings = scan_and_strip_content(content)
        assert key not in cleaned
        assert PLACEHOLDER in cleaned

    @given(prefix=_safe_text, key=_sk_key, suffix=_safe_text)
    @settings(max_examples=100, deadline=5_000)
    def test_sk_api_key_redacted(self, prefix, key, suffix):
        """sk- API keys are redacted."""
        content = f"{prefix}{key}{suffix}"
        cleaned, findings = scan_and_strip_content(content)
        assert key not in cleaned
        assert PLACEHOLDER in cleaned

    @given(prefix=_safe_text, token=_github_token(), suffix=_safe_text)
    @settings(max_examples=100, deadline=5_000)
    def test_github_token_redacted(self, prefix, token, suffix):
        """GitHub fine-grained/classic tokens (ghp_, gho_, ghs_, ghu_, ghr_) are redacted."""
        content = f"{prefix}{token}{suffix}"
        cleaned, findings = scan_and_strip_content(content)
        assert token not in cleaned
        assert PLACEHOLDER in cleaned

    @given(prefix=_safe_text, token=_github_pat_legacy, suffix=_safe_text)
    @settings(max_examples=100, deadline=5_000)
    def test_github_pat_legacy_redacted(self, prefix, token, suffix):
        """Legacy GitHub PATs (github_pat_) are redacted."""
        content = f"{prefix}{token}{suffix}"
        cleaned, findings = scan_and_strip_content(content)
        assert token not in cleaned
        assert PLACEHOLDER in cleaned

    @given(prefix=_safe_text, header=_pem_header, suffix=_safe_text)
    @settings(max_examples=100, deadline=5_000)
    def test_pem_header_redacted(self, prefix, header, suffix):
        """PEM private key headers are redacted."""
        content = f"{prefix}{header}{suffix}"
        cleaned, findings = scan_and_strip_content(content)
        assert header not in cleaned
        assert PLACEHOLDER in cleaned

    @given(prefix=_safe_text, assignment=_high_entropy, suffix=_safe_text)
    @settings(max_examples=100, deadline=5_000)
    def test_high_entropy_assignment_redacted(self, prefix, assignment, suffix):
        """High-entropy secret assignments are redacted."""
        content = f"{prefix}{assignment}{suffix}"
        cleaned, findings = scan_and_strip_content(content)
        assert PLACEHOLDER in cleaned
