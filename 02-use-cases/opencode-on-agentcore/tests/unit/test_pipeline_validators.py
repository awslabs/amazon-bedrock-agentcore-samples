# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for the ``_validate_repo_url`` and ``_validate_git_ref`` guards
in :mod:`container.pipeline`.

The validators exist to produce clearer errors for obviously malformed
``repo_url`` / branch-name inputs than git would surface five frames
deeper in the call stack. They are **not** the sandbox boundary -
``container.pipeline`` invokes git via ``subprocess.run`` with
list-form argv, so shell injection is impossible regardless of input
(documented in the PCSR triage, Rule 11).

These tests lock the exact contract so a future refactor cannot
silently relax it.
"""

from __future__ import annotations

import pytest

from container.pipeline import _validate_git_ref, _validate_repo_url


# ---------------------------------------------------------------------------
# _validate_repo_url
# ---------------------------------------------------------------------------


class TestValidateRepoUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/owner/repo",
            "https://github.com/owner/repo.git",
            "https://gitlab.example.com/group/project.git",
            "git@github.com:owner/repo.git",
            "https://github.com/owner/" + "a" * 100,
            # Non-ASCII path segments are allowed (git lets them through).
            "https://github.com/owner/ŀÙ𭂃",
        ],
    )
    def test_accepts_well_formed_urls(self, url: str) -> None:
        _validate_repo_url(url)  # should not raise

    @pytest.mark.parametrize(
        "bad_url",
        [
            "",
            "http://github.com/owner/repo",          # plain http not allowed
            "ftp://github.com/owner/repo",           # wrong scheme
            "github.com/owner/repo",                 # missing scheme
            "https:/typo.com/x",                     # malformed scheme
            "https://github.com/owner/repo\x00hi",   # NUL
            "https://github.com/owner/re po",        # embedded space
            "https://github.com/owner/\nnewline",    # embedded newline
            "https://github.com/owner/\ttab",        # embedded tab
            "https://" + "x" * 2050,                 # over 2048 chars
        ],
    )
    def test_rejects_malformed_urls(self, bad_url: str) -> None:
        with pytest.raises(ValueError):
            _validate_repo_url(bad_url)

    def test_rejects_non_string_input(self) -> None:
        with pytest.raises(ValueError):
            _validate_repo_url(None)  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            _validate_repo_url(42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _validate_git_ref
# ---------------------------------------------------------------------------


class TestValidateGitRef:
    @pytest.mark.parametrize(
        "ref",
        [
            "main",
            "develop",
            "feature/add-thing",
            "release/1.2.3",
            "fix_bug",
            # Non-ASCII branch names - git allows these.
            "feature/日本語",
            # Long but within the 255-char cap.
            "a" * 255,
        ],
    )
    def test_accepts_well_formed_refs(self, ref: str) -> None:
        _validate_git_ref(ref, "base_branch")

    @pytest.mark.parametrize(
        "bad_ref",
        [
            "",
            "-force-flag",            # argv-flag confusion with git
            "--really-a-flag",        # same, double-dash
            "-n",                     # matches common CLI flags
            "ref with space",
            "ref\nwith-newline",
            "ref\twith-tab",
            "ref\x00with-nul",
            "a" * 256,                # over the 255-char cap
        ],
    )
    def test_rejects_malformed_refs(self, bad_ref: str) -> None:
        with pytest.raises(ValueError):
            _validate_git_ref(bad_ref, "base_branch")

    def test_rejects_non_string_input(self) -> None:
        with pytest.raises(ValueError):
            _validate_git_ref(None, "base_branch")  # type: ignore[arg-type]
        with pytest.raises(ValueError):
            _validate_git_ref(42, "base_branch")  # type: ignore[arg-type]

    def test_error_uses_provided_label(self) -> None:
        """The label argument appears in the exception message so callers
        can identify whether ``base_branch`` or ``target_branch`` is bad."""
        with pytest.raises(ValueError, match="target_branch"):
            _validate_git_ref("", "target_branch")
        with pytest.raises(ValueError, match="base_branch"):
            _validate_git_ref("", "base_branch")
