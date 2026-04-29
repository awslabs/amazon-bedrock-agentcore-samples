# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for scan_and_strip_credentials tool.

Requirements: 9.4, 21.1, 21.2, 21.3, 21.4, 21.5
"""

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from container.tools.scan_and_strip_credentials import (
    PATTERNS,
    PLACEHOLDER,
    ScanResult,
    scan_and_strip_content,
    scan_and_strip_credentials_impl,
)


# ---------------------------------------------------------------------------
# scan_and_strip_content — pure function tests
# ---------------------------------------------------------------------------


class TestScanAndStripContent:
    """Tests for the pure scan_and_strip_content helper."""

    def test_detects_aws_access_key(self):
        content = "aws_key = AKIAIOSFODNN7EXAMPLE"
        cleaned, findings = scan_and_strip_content(content)
        assert PLACEHOLDER in cleaned
        assert "AKIAIOSFODNN7EXAMPLE" not in cleaned
        assert len(findings) == 1
        assert findings[0]["pattern"] == "AWS Access Key"

    def test_detects_sk_api_key(self):
        content = 'api_key = "sk-abcdefghijklmnopqrstuvwx"'
        cleaned, findings = scan_and_strip_content(content)
        assert PLACEHOLDER in cleaned
        assert "sk-abcdefghijklmnopqrstuvwx" not in cleaned
        assert any(f["pattern"] == "API Key (sk-)" for f in findings)

    def test_detects_pem_private_key(self):
        content = "-----BEGIN RSA PRIVATE KEY-----\nMIIE..."
        cleaned, findings = scan_and_strip_content(content)
        assert PLACEHOLDER in cleaned
        assert "-----BEGIN RSA PRIVATE KEY-----" not in cleaned
        assert any(f["pattern"] == "PEM Private Key" for f in findings)

    def test_detects_generic_private_key(self):
        content = "-----BEGIN PRIVATE KEY-----"
        cleaned, findings = scan_and_strip_content(content)
        assert PLACEHOLDER in cleaned
        assert any(f["pattern"] == "PEM Private Key" for f in findings)

    def test_detects_high_entropy_assignment(self):
        secret_value = "A" * 25
        content = f'secret = "{secret_value}"'
        cleaned, findings = scan_and_strip_content(content)
        assert PLACEHOLDER in cleaned
        assert any(f["pattern"] == "High-entropy assignment" for f in findings)

    def test_high_entropy_case_insensitive(self):
        secret_value = "B" * 25
        content = f"SECRET = '{secret_value}'"
        cleaned, findings = scan_and_strip_content(content)
        assert PLACEHOLDER in cleaned
        assert len(findings) >= 1

    def test_no_credentials_returns_unchanged(self):
        content = "print('hello world')\nx = 42\n"
        cleaned, findings = scan_and_strip_content(content)
        assert cleaned == content
        assert findings == []

    def test_multiple_patterns_in_same_content(self):
        content = (
            "key1 = AKIAIOSFODNN7EXAMPLE\n"
            "key2 = sk-abcdefghijklmnopqrstuvwx\n"
            "-----BEGIN PRIVATE KEY-----\n"
        )
        cleaned, findings = scan_and_strip_content(content)
        assert cleaned.count(PLACEHOLDER) == 3
        pattern_names = {f["pattern"] for f in findings}
        assert "AWS Access Key" in pattern_names
        assert "API Key (sk-)" in pattern_names
        assert "PEM Private Key" in pattern_names

    # --- New patterns (Req 12) ---

    def test_detects_aws_temp_credentials(self):
        content = "temp_key = ASIAJEXAMPLEKEYID1234"
        cleaned, findings = scan_and_strip_content(content)
        assert PLACEHOLDER in cleaned
        assert "ASIAJEXAMPLEKEYID1234" not in cleaned
        assert any(f["pattern"] == "AWS Temp Credentials" for f in findings)

    def test_detects_github_fine_grained_token_ghp(self):
        token = "ghp_" + "A" * 36
        content = f"GITHUB_TOKEN={token}"
        cleaned, findings = scan_and_strip_content(content)
        assert PLACEHOLDER in cleaned
        assert token not in cleaned
        assert any(f["pattern"] == "GitHub Token" for f in findings)

    def test_detects_github_token_gho(self):
        token = "gho_" + "B" * 36
        content = f"token = {token}"
        cleaned, findings = scan_and_strip_content(content)
        assert PLACEHOLDER in cleaned
        assert token not in cleaned
        assert any(f["pattern"] == "GitHub Token" for f in findings)

    def test_detects_github_token_ghs(self):
        token = "ghs_" + "C" * 40
        content = f"GH_TOKEN={token}"
        cleaned, findings = scan_and_strip_content(content)
        assert PLACEHOLDER in cleaned
        assert token not in cleaned
        assert any(f["pattern"] == "GitHub Token" for f in findings)

    def test_detects_github_token_ghu(self):
        token = "ghu_" + "D" * 36
        content = f"auth={token}"
        cleaned, findings = scan_and_strip_content(content)
        assert PLACEHOLDER in cleaned
        assert token not in cleaned
        assert any(f["pattern"] == "GitHub Token" for f in findings)

    def test_detects_github_token_ghr(self):
        token = "ghr_" + "E" * 36
        content = f"refresh={token}"
        cleaned, findings = scan_and_strip_content(content)
        assert PLACEHOLDER in cleaned
        assert token not in cleaned
        assert any(f["pattern"] == "GitHub Token" for f in findings)

    def test_detects_github_pat_legacy(self):
        token = "github_pat_" + "F" * 22
        content = f"PAT={token}"
        cleaned, findings = scan_and_strip_content(content)
        assert PLACEHOLDER in cleaned
        assert token not in cleaned
        assert any(f["pattern"] == "GitHub PAT (legacy)" for f in findings)

    def test_detects_gitlab_pat(self):
        token = "glpat-" + "a" * 20
        content = f"GITLAB_TOKEN={token}"
        cleaned, findings = scan_and_strip_content(content)
        assert PLACEHOLDER in cleaned
        assert token not in cleaned
        assert any(f["pattern"] == "GitLab PAT" for f in findings)

    def test_gitlab_pat_with_hyphens_and_underscores(self):
        token = "glpat-" + "a_b-c" * 5
        content = f"token={token}"
        cleaned, findings = scan_and_strip_content(content)
        assert PLACEHOLDER in cleaned
        assert token not in cleaned
        assert any(f["pattern"] == "GitLab PAT" for f in findings)

    def test_match_truncated_to_40_chars(self):
        long_key = "sk-" + "a" * 60
        content = f"key = {long_key}"
        _, findings = scan_and_strip_content(content)
        assert len(findings) == 1
        assert len(findings[0]["match"]) <= 40


# ---------------------------------------------------------------------------
# scan_and_strip_credentials — tool integration tests (uses tmp git repo)
# ---------------------------------------------------------------------------


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a minimal git repo with an initial commit."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    # Initial commit so HEAD exists
    readme = tmp_path / "README.md"
    readme.write_text("# test\n")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    return tmp_path


class TestScanAndStripCredentialsTool:
    """Integration tests using a real git repo."""

    def test_scans_modified_file_and_strips(self, git_repo: Path):
        secret_file = git_repo / "config.py"
        secret_file.write_text('AWS_KEY = "AKIAIOSFODNN7EXAMPLE"\n')
        subprocess.run(["git", "add", "."], cwd=str(git_repo), check=True, capture_output=True)

        result = scan_and_strip_credentials_impl(
            work_dir=str(git_repo), job_id="test-job-1"
        )

        assert result["files_scanned"] >= 1
        assert result["files_modified"] >= 1
        assert len(result["findings"]) >= 1
        # Verify the file was actually cleaned
        assert PLACEHOLDER in secret_file.read_text()
        assert "AKIAIOSFODNN7EXAMPLE" not in secret_file.read_text()

    def test_no_modified_files_returns_zeros(self, git_repo: Path):
        result = scan_and_strip_credentials_impl(
            work_dir=str(git_repo), job_id="test-job-2"
        )
        assert result["files_scanned"] == 0
        assert result["files_modified"] == 0
        assert result["findings"] == []

    def test_clean_file_not_modified(self, git_repo: Path):
        clean_file = git_repo / "clean.py"
        clean_file.write_text("x = 42\n")
        subprocess.run(["git", "add", "."], cwd=str(git_repo), check=True, capture_output=True)

        result = scan_and_strip_credentials_impl(
            work_dir=str(git_repo), job_id="test-job-3"
        )

        assert result["files_scanned"] >= 1
        assert result["files_modified"] == 0
        assert result["findings"] == []

    def test_untracked_files_also_scanned(self, git_repo: Path):
        untracked = git_repo / "leak.txt"
        untracked.write_text("-----BEGIN RSA PRIVATE KEY-----\n")
        # Don't git add — file is untracked

        result = scan_and_strip_credentials_impl(
            work_dir=str(git_repo), job_id="test-job-4"
        )

        assert result["files_scanned"] >= 1
        assert result["files_modified"] >= 1
        assert PLACEHOLDER in untracked.read_text()

    def test_findings_include_file_path(self, git_repo: Path):
        secret_file = git_repo / "secrets.env"
        secret_file.write_text('token = "sk-abcdefghijklmnopqrstuvwx"\n')
        subprocess.run(["git", "add", "."], cwd=str(git_repo), check=True, capture_output=True)

        result = scan_and_strip_credentials_impl(
            work_dir=str(git_repo), job_id="test-job-5"
        )

        assert len(result["findings"]) >= 1
        assert result["findings"][0]["file"] == "secrets.env"

    def test_multiple_files_with_mixed_content(self, git_repo: Path):
        (git_repo / "a.py").write_text("clean code\n")
        (git_repo / "b.py").write_text("key = AKIAIOSFODNN7EXAMPLE\n")
        (git_repo / "c.py").write_text("more clean code\n")
        subprocess.run(["git", "add", "."], cwd=str(git_repo), check=True, capture_output=True)

        result = scan_and_strip_credentials_impl(
            work_dir=str(git_repo), job_id="test-job-6"
        )

        assert result["files_scanned"] >= 3
        assert result["files_modified"] == 1
