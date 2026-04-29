# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for git_push_and_create_pr tool.

Requirements: 2.1, 2.2, 2.3, 2.4, 15.1, 15.2
"""

import json
import logging
import sys
import urllib.error
from unittest.mock import patch, MagicMock

# Stub strands before importing the module under test
strands_mock = MagicMock()
strands_mock.tool = lambda fn: fn
sys.modules.setdefault("strands", strands_mock)

from container.tools.git_push_and_create_pr import git_push_and_create_pr


def _make_subprocess_mock():
    """Create a subprocess.run mock that simulates successful git operations."""
    mock = MagicMock()
    diff_result = MagicMock()
    diff_result.stdout = "file.py | 1 +\n"

    def side_effect(cmd, **kwargs):
        if cmd[1:3] == ["diff", "--cached"]:
            return diff_result
        return MagicMock()

    mock.side_effect = side_effect
    return mock


def _make_urlopen_response(body: dict):
    """Create a mock urlopen response returning JSON body."""
    resp = MagicMock()
    resp.read.return_value = json.dumps(body).encode()
    return resp


class TestPRCreationUsesUrllib:
    """Test that PR creation uses urllib.request instead of curl subprocess."""

    @patch("container.tools.git_push_and_create_pr.urllib.request.urlopen")
    @patch("container.tools.git_push_and_create_pr.subprocess.run")
    def test_no_curl_in_subprocess_calls(self, mock_run, mock_urlopen):
        mock_run.side_effect = _make_subprocess_mock().side_effect
        mock_urlopen.return_value = _make_urlopen_response(
            {"html_url": "https://github.com/o/r/pull/1"}
        )

        git_push_and_create_pr(
            work_dir="/tmp/w",
            token="ghp_secret",
            repo_url="https://github.com/owner/repo",
            target_branch="feat",
            base_branch="main",
            task_description="task",
            job_id="j1",
        )

        for call_obj in mock_run.call_args_list:
            cmd = call_obj[0][0]
            assert cmd[0] != "curl", "curl should not be called as a subprocess"

    @patch("container.tools.git_push_and_create_pr.urllib.request.urlopen")
    @patch("container.tools.git_push_and_create_pr.subprocess.run")
    def test_token_not_in_subprocess_args(self, mock_run, mock_urlopen):
        mock_run.side_effect = _make_subprocess_mock().side_effect
        mock_urlopen.return_value = _make_urlopen_response(
            {"html_url": "https://github.com/o/r/pull/1"}
        )
        token = "ghp_supersecrettoken123456"

        git_push_and_create_pr(
            work_dir="/tmp/w",
            token=token,
            repo_url="https://github.com/owner/repo",
            target_branch="feat",
            base_branch="main",
            task_description="task",
            job_id="j1",
        )

        for call_obj in mock_run.call_args_list:
            for arg in call_obj[0][0]:
                assert token not in arg

    @patch("container.tools.git_push_and_create_pr.urllib.request.urlopen")
    @patch("container.tools.git_push_and_create_pr.subprocess.run")
    def test_urlopen_called_with_correct_url(self, mock_run, mock_urlopen):
        mock_run.side_effect = _make_subprocess_mock().side_effect
        mock_urlopen.return_value = _make_urlopen_response(
            {"html_url": "https://github.com/myorg/myrepo/pull/42"}
        )

        git_push_and_create_pr(
            work_dir="/tmp/w",
            token="ghp_tok",
            repo_url="https://github.com/myorg/myrepo",
            target_branch="feat",
            base_branch="main",
            task_description="task",
            job_id="j1",
        )

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "https://api.github.com/repos/myorg/myrepo/pulls"
        assert req.get_header("Authorization") == "Bearer ghp_tok"
        assert req.get_method() == "POST"


class TestPRCreationSuccessResponse:
    """Test successful PR creation returns html_url."""

    @patch("container.tools.git_push_and_create_pr.urllib.request.urlopen")
    @patch("container.tools.git_push_and_create_pr.subprocess.run")
    def test_returns_html_url(self, mock_run, mock_urlopen):
        mock_run.side_effect = _make_subprocess_mock().side_effect
        expected_url = "https://github.com/owner/repo/pull/99"
        mock_urlopen.return_value = _make_urlopen_response(
            {"html_url": expected_url, "id": 12345}
        )

        result = git_push_and_create_pr(
            work_dir="/tmp/w",
            token="ghp_tok",
            repo_url="https://github.com/owner/repo",
            target_branch="feat",
            base_branch="main",
            task_description="task",
            job_id="j1",
        )

        assert result["pr_url"] == expected_url
        assert result["pushed"] is True

    @patch("container.tools.git_push_and_create_pr.urllib.request.urlopen")
    @patch("container.tools.git_push_and_create_pr.subprocess.run")
    def test_returns_none_when_no_html_url_in_response(self, mock_run, mock_urlopen):
        mock_run.side_effect = _make_subprocess_mock().side_effect
        mock_urlopen.return_value = _make_urlopen_response({"id": 12345})

        result = git_push_and_create_pr(
            work_dir="/tmp/w",
            token="ghp_tok",
            repo_url="https://github.com/owner/repo",
            target_branch="feat",
            base_branch="main",
            task_description="task",
            job_id="j1",
        )

        assert result["pr_url"] is None
        assert result["pushed"] is True


class TestPRCreationErrorLogging:
    """Test that errors are logged at WARNING level and fallback is returned."""

    @patch("container.tools.git_push_and_create_pr.urllib.request.urlopen")
    @patch("container.tools.git_push_and_create_pr.subprocess.run")
    def test_http_error_logged_at_warning(self, mock_run, mock_urlopen, caplog):
        mock_run.side_effect = _make_subprocess_mock().side_effect
        http_error = urllib.error.HTTPError(
            url="https://api.github.com/repos/o/r/pulls",
            code=422,
            msg="Unprocessable Entity",
            hdrs={},
            fp=MagicMock(read=MagicMock(return_value=b'{"message":"Validation Failed"}')),
        )
        mock_urlopen.side_effect = http_error

        with caplog.at_level(logging.WARNING, logger="container.tools.git_push_and_create_pr"):
            result = git_push_and_create_pr(
                work_dir="/tmp/w",
                token="ghp_tok",
                repo_url="https://github.com/owner/repo",
                target_branch="feat",
                base_branch="main",
                task_description="task",
                job_id="j1",
            )

        assert result == {"pr_url": None, "pushed": True}
        assert any("HTTP error 422" in r.message for r in caplog.records)

    @patch("container.tools.git_push_and_create_pr.urllib.request.urlopen")
    @patch("container.tools.git_push_and_create_pr.subprocess.run")
    def test_url_error_logged_at_warning(self, mock_run, mock_urlopen, caplog):
        mock_run.side_effect = _make_subprocess_mock().side_effect
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        with caplog.at_level(logging.WARNING, logger="container.tools.git_push_and_create_pr"):
            result = git_push_and_create_pr(
                work_dir="/tmp/w",
                token="ghp_tok",
                repo_url="https://github.com/owner/repo",
                target_branch="feat",
                base_branch="main",
                task_description="task",
                job_id="j1",
            )

        assert result == {"pr_url": None, "pushed": True}
        assert any("URL error" in r.message for r in caplog.records)

    @patch("container.tools.git_push_and_create_pr.urllib.request.urlopen")
    @patch("container.tools.git_push_and_create_pr.subprocess.run")
    def test_json_parse_error_logged_at_warning(self, mock_run, mock_urlopen, caplog):
        mock_run.side_effect = _make_subprocess_mock().side_effect
        resp_mock = MagicMock()
        resp_mock.read.return_value = b"not valid json{{"
        mock_urlopen.return_value = resp_mock

        with caplog.at_level(logging.WARNING, logger="container.tools.git_push_and_create_pr"):
            result = git_push_and_create_pr(
                work_dir="/tmp/w",
                token="ghp_tok",
                repo_url="https://github.com/owner/repo",
                target_branch="feat",
                base_branch="main",
                task_description="task",
                job_id="j1",
            )

        assert result == {"pr_url": None, "pushed": True}
        assert any("parse" in r.message.lower() for r in caplog.records)

    @patch("container.tools.git_push_and_create_pr.urllib.request.urlopen")
    @patch("container.tools.git_push_and_create_pr.subprocess.run")
    def test_http_403_error_returns_fallback(self, mock_run, mock_urlopen):
        mock_run.side_effect = _make_subprocess_mock().side_effect
        http_error = urllib.error.HTTPError(
            url="https://api.github.com/repos/o/r/pulls",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=MagicMock(read=MagicMock(return_value=b'{"message":"rate limit"}')),
        )
        mock_urlopen.side_effect = http_error

        result = git_push_and_create_pr(
            work_dir="/tmp/w",
            token="ghp_tok",
            repo_url="https://github.com/owner/repo",
            target_branch="feat",
            base_branch="main",
            task_description="task",
            job_id="j1",
        )

        assert result == {"pr_url": None, "pushed": True}


class TestPRCreationNonGitHubRepo:
    """Test behavior when repo URL doesn't match GitHub pattern."""

    @patch("container.tools.git_push_and_create_pr.subprocess.run")
    def test_non_github_url_returns_pushed_true_no_pr(self, mock_run):
        mock_run.side_effect = _make_subprocess_mock().side_effect

        result = git_push_and_create_pr(
            work_dir="/tmp/w",
            token="ghp_tok",
            repo_url="https://gitlab.com/owner/repo",
            target_branch="feat",
            base_branch="main",
            task_description="task",
            job_id="j1",
        )

        assert result == {"pr_url": None, "pushed": True}


class TestPRCreationNoDiff:
    """Test behavior when there are no changes to commit."""

    @patch("container.tools.git_push_and_create_pr.subprocess.run")
    def test_no_changes_returns_not_pushed(self, mock_run):
        diff_result = MagicMock()
        diff_result.stdout = ""

        def side_effect(cmd, **kwargs):
            if cmd[1:3] == ["diff", "--cached"]:
                return diff_result
            return MagicMock()

        mock_run.side_effect = side_effect

        result = git_push_and_create_pr(
            work_dir="/tmp/w",
            token="ghp_tok",
            repo_url="https://github.com/owner/repo",
            target_branch="feat",
            base_branch="main",
            task_description="task",
            job_id="j1",
        )

        assert result == {"pr_url": None, "pushed": False}
