# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Naming consistency tests for the unified runtime.

Validates: Requirements 9.1, 9.2, 9.6

After runtime consolidation, the codebase should not contain any
references to the old split names ``opencode-coding`` or
``opencode-control``.  All MCP auto-approve entries should use the
unified ``opencode___`` prefix.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Directories and files that are allowed to reference old names.
EXCLUDED_DIRS = {
    ".kiro/specs",
    ".git",
    ".hypothesis",
    "connect_git_host_container",
    "cdk.out",       # CDK synthesis output (may contain stale assets)
    "tmp",           # Temporary / scratch files
    "__pycache__",
    ".pytest_cache",
}

EXCLUDED_FILES = {
    "tests/unit/test_naming_consistency.py",   # This file references old names in test logic
}

# File extensions considered "source files" for the naming scan.
SOURCE_EXTENSIONS = {
    ".py", ".ts", ".js", ".json", ".yaml", ".yml", ".toml", ".cfg",
    ".md", ".txt", ".sh", ".bash", ".env", ".ini",
}


def _is_excluded(path: Path) -> bool:
    """Return True if *path* falls under an excluded directory or file."""
    rel = path.relative_to(PROJECT_ROOT).as_posix()
    for excl_dir in EXCLUDED_DIRS:
        if rel.startswith(excl_dir + "/") or rel == excl_dir:
            return True
    for excl_file in EXCLUDED_FILES:
        if rel == excl_file:
            return True
    return False


def _source_files() -> list[Path]:
    """Collect all source files in the project, respecting exclusions."""
    files: list[Path] = []
    for p in PROJECT_ROOT.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix not in SOURCE_EXTENSIONS:
            continue
        if _is_excluded(p):
            continue
        files.append(p)
    return files


def _find_references(pattern: str) -> list[tuple[str, int, str]]:
    """Return (relative_path, line_number, line_text) for every match."""
    hits: list[tuple[str, int, str]] = []
    for path in _source_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern in line:
                rel = path.relative_to(PROJECT_ROOT).as_posix()
                hits.append((rel, lineno, line.strip()))
    return hits


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNoOldNamingReferences:
    """Ensure old split names are gone from the codebase."""

    def test_no_opencode_coding_references(self):
        """No source files contain 'opencode-coding' as a target/server/prefix name.

        Validates: Requirement 9.1
        """
        hits = _find_references("opencode-coding")
        assert hits == [], (
            f"Found {len(hits)} reference(s) to 'opencode-coding':\n"
            + "\n".join(f"  {f}:{ln}: {txt}" for f, ln, txt in hits)
        )

