# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property test: No Secrets in Output.

**Validates: Requirements 14.1, 14.2**

Property 4 — No Secrets in Output:
  - Generated code containing embedded secrets must have all secrets detected and stripped.
  - No false negatives for known patterns (AWS keys, sk- keys, PEM headers).

Tests the credential scanner regex patterns in Python (mirroring the JS patterns).
"""

from __future__ import annotations

import re

from hypothesis import given, settings
from hypothesis import strategies as st

# Mirror the JS scanner patterns
PATTERNS = [
    ("AWS Access Key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("API Key (sk-)", re.compile(r"sk-[a-zA-Z0-9]{20,}")),
    ("PEM Private Key", re.compile(r"-----BEGIN[A-Z ]*PRIVATE KEY-----")),
]

PLACEHOLDER = "<REDACTED_SECRET>"


def scan_and_strip(content: str) -> str:
    result = content
    for _, pattern in PATTERNS:
        result = pattern.sub(PLACEHOLDER, result)
    return result


def has_secret(content: str) -> bool:
    return any(p.search(content) for _, p in PATTERNS)


# Strategies for generating secrets
aws_key = st.from_regex(r"AKIA[0-9A-Z]{16}", fullmatch=True)
sk_key = st.from_regex(r"sk-[a-zA-Z0-9]{24}", fullmatch=True)
pem_header = st.just("-----BEGIN RSA PRIVATE KEY-----")

secret_strategy = st.one_of(aws_key, sk_key, pem_header)
prefix_strategy = st.text(min_size=0, max_size=50, alphabet="abcdefghijklmnop \n=:")
suffix_strategy = st.text(min_size=0, max_size=50, alphabet="abcdefghijklmnop \n;")


class TestNoSecretsInOutput:
    @given(secret=secret_strategy, prefix=prefix_strategy, suffix=suffix_strategy)
    @settings(max_examples=50, deadline=5_000)
    def test_embedded_secrets_are_detected(self, secret, prefix, suffix):
        """Any known secret pattern embedded in code must be detected."""
        content = f"{prefix}{secret}{suffix}"
        assert has_secret(content), f"Secret not detected: {secret[:20]}..."

    @given(secret=secret_strategy, prefix=prefix_strategy, suffix=suffix_strategy)
    @settings(max_examples=50, deadline=5_000)
    def test_stripped_output_has_no_secrets(self, secret, prefix, suffix):
        """After stripping, no known secret patterns remain."""
        content = f"{prefix}{secret}{suffix}"
        stripped = scan_and_strip(content)
        assert not has_secret(stripped), f"Secret survived stripping in: {stripped[:100]}"

    @given(secret=secret_strategy)
    @settings(max_examples=30, deadline=5_000)
    def test_placeholder_replaces_secret(self, secret):
        """Stripped content contains the placeholder."""
        stripped = scan_and_strip(secret)
        assert PLACEHOLDER in stripped

    def test_clean_code_passes(self):
        """Code without secrets passes through unchanged."""
        code = 'const x = "hello world";\nfunction foo() { return 42; }'
        assert scan_and_strip(code) == code
        assert not has_secret(code)

    @given(st.lists(secret_strategy, min_size=1, max_size=5))
    @settings(max_examples=30, deadline=5_000)
    def test_multiple_secrets_all_stripped(self, secrets):
        """Multiple secrets in one file are all stripped."""
        content = "\n".join(f"line: {s}" for s in secrets)
        stripped = scan_and_strip(content)
        assert not has_secret(stripped)
