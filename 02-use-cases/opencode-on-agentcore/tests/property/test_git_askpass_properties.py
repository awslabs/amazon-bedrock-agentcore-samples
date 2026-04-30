# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Property-based preservation tests for ``_create_askpass_script``.

**Validates: Requirements 3.5, 3.6**

Property 8 (Preservation): for any token that does NOT hit the Finding 3
bug condition (alphanumeric/underscore tokens), ``bash <script_path>``
on the current code produces ``token + "\\n"`` on stdout with exit 0.
After the fix, the same property must hold.

These tests MUST PASS on unfixed code and continue to PASS after the fix.

.. note::

   Any string literal in this file that matches a ``gh[pousr]_`` or
   similar OAuth-token prefix is a **synthetic test fixture**, not a
   real credential. The tests exercise the askpass shell-escaping
   machinery, which needs realistic-shaped inputs (right length, right
   prefix, right alphabet) to give meaningful coverage. Every such
   literal is either hypothesis-generated at test time or a short,
   obviously-fake string ending in ``0123`` or similar sequential
   digits. Credential scanners (trufflehog, secretlint) should allow
   these values via this file's path.
"""

from __future__ import annotations

import os
import subprocess

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from container.lib.git_askpass import _create_askpass_script

# ---------------------------------------------------------------------------
# Strategy: alphanumeric/underscore tokens (non-bug-condition tokens)
# ---------------------------------------------------------------------------

_SAFE_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"

_safe_token = st.text(
    alphabet=_SAFE_ALPHABET,
    min_size=1,
    max_size=256,
)


# ---------------------------------------------------------------------------
# Property: alphanumeric tokens produce token + "\n" via bash
# ---------------------------------------------------------------------------


class TestAskpassAlphanumericPreservation:
    """For every alphanumeric/underscore token, the askpass script prints
    ``token + "\\n"`` on stdout with exit 0.

    **Validates: Requirements 3.5**

    This is the preservation property for Finding 3: tokens that do NOT
    hit the bug condition (no single quotes, no ``-n``/``-e``/``-E``
    prefix) work correctly on both unfixed and fixed code.
    """

    @given(token=_safe_token)
    @settings(
        max_examples=50,
        deadline=None,
        suppress_health_check=[HealthCheck.too_slow],
    )
    def test_safe_token_prints_token_newline(self, token: str) -> None:
        script_path = _create_askpass_script(token)
        sidecar = script_path + ".token"
        try:
            result = subprocess.run(
                ["bash", script_path],
                capture_output=True,
                timeout=10,
            )
            assert result.returncode == 0, (
                f"bash askpass must exit 0 for safe token {token!r}; "
                f"stderr={result.stderr!r}, returncode={result.returncode}"
            )
            assert result.stdout == token.encode("utf-8") + b"\n", (
                f"bash askpass must print token+newline for safe token "
                f"{token!r}; stdout={result.stdout!r}"
            )
        finally:
            for p in (script_path, sidecar):
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

    def test_create_askpass_script_returns_single_string(self) -> None:
        """``_create_askpass_script`` returns a single ``str``, not a tuple
        or other container. This signature must be preserved so existing
        test patches (``return_value="/tmp/fake_askpass.sh"``) continue
        to work.

        **Validates: Requirements 3.6**
        """
        result = _create_askpass_script("ghp_0123456789abcdef0123456789abcdef0123")  # test-fixture; not a real token
        sidecar = result + ".token"
        try:
            assert isinstance(result, str), (
                f"_create_askpass_script must return str; got {type(result)}"
            )
            assert not isinstance(result, (list, tuple)), (
                f"_create_askpass_script must not return a sequence; got {type(result)}"
            )
        finally:
            for p in (result, sidecar):
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

    def test_deterministic_github_pat(self) -> None:
        """A typical GitHub PAT (``ghp_`` prefix + 36 alphanumerics) prints
        correctly. Deterministic sanity check."""
        token = "ghp_0123456789abcdef0123456789abcdef0123"  # test-fixture; not a real token
        script_path = _create_askpass_script(token)
        sidecar = script_path + ".token"
        try:
            result = subprocess.run(
                ["bash", script_path],
                capture_output=True,
                timeout=10,
            )
            assert result.returncode == 0
            assert result.stdout == token.encode("utf-8") + b"\n"
        finally:
            for p in (script_path, sidecar):
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
