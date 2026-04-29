# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for git_clone tool.

Requirements: 1.1, 1.2, 1.3, 1.4
"""

import os
import subprocess
import sys
from unittest.mock import patch, MagicMock

# Stub strands before importing the module under test
strands_mock = MagicMock()
strands_mock.tool = lambda fn: fn  # @tool is identity decorator for testing
sys.modules.setdefault("strands", strands_mock)

from container.tools.git_clone import git_clone, _create_askpass_script


class TestCreateAskpassScript:
    """Test the _create_askpass_script helper."""

    def test_creates_file_that_exists(self):
        path = _create_askpass_script("test-token")
        try:
            assert os.path.exists(path)
        finally:
            sidecar = path + ".token"
            if os.path.exists(sidecar):
                os.remove(sidecar)
            os.remove(path)

    def test_script_contains_cat_sidecar(self):
        path = _create_askpass_script("my-secret-token")
        try:
            with open(path) as f:
                content = f.read()
            assert 'cat "$0.token"' in content
            assert content.startswith("#!/bin/sh\n")
        finally:
            sidecar = path + ".token"
            if os.path.exists(sidecar):
                os.remove(sidecar)
            os.remove(path)

    def test_script_is_owner_executable(self):
        import stat
        path = _create_askpass_script("tok")
        try:
            mode = os.stat(path).st_mode
            assert mode & stat.S_IRUSR  # owner read
            assert mode & stat.S_IXUSR  # owner execute
            assert not (mode & stat.S_IRGRP)  # no group read
            assert not (mode & stat.S_IROTH)  # no other read
        finally:
            sidecar = path + ".token"
            if os.path.exists(sidecar):
                os.remove(sidecar)
            os.remove(path)

    def test_script_has_sh_suffix(self):
        path = _create_askpass_script("tok")
        try:
            assert path.endswith(".sh")
        finally:
            sidecar = path + ".token"
            if os.path.exists(sidecar):
                os.remove(sidecar)
            os.remove(path)


class TestGitCloneAskpass:
    """Test that git_clone uses GIT_ASKPASS and does not embed token in URL."""

    @patch("container.tools.git_clone.subprocess.run")
    @patch("container.tools.git_clone._create_askpass_script", return_value="/tmp/fake_askpass.sh")
    @patch("container.tools.git_clone.os.path.exists", return_value=True)
    @patch("container.tools.git_clone.os.remove")
    def test_token_not_in_clone_url(self, mock_remove, mock_exists, mock_askpass, mock_run):
        git_clone(
            repo_url="https://github.com/owner/repo",
            token="ghp_test123",
            base_branch="main",
            work_dir="/tmp/work",
        )

        args = mock_run.call_args[0][0]
        for arg in args:
            assert "ghp_test123" not in arg

    @patch("container.tools.git_clone.subprocess.run")
    @patch("container.tools.git_clone._create_askpass_script", return_value="/tmp/fake_askpass.sh")
    @patch("container.tools.git_clone.os.path.exists", return_value=True)
    @patch("container.tools.git_clone.os.remove")
    def test_clone_url_has_username_only(self, mock_remove, mock_exists, mock_askpass, mock_run):
        git_clone(
            repo_url="https://github.com/owner/repo",
            token="ghp_test123",
            base_branch="main",
            work_dir="/tmp/work",
        )

        args = mock_run.call_args[0][0]
        assert "https://x-access-token@github.com/owner/repo" in args

    @patch("container.tools.git_clone.subprocess.run")
    @patch("container.tools.git_clone._create_askpass_script", return_value="/tmp/fake_askpass.sh")
    @patch("container.tools.git_clone.os.path.exists", return_value=True)
    @patch("container.tools.git_clone.os.remove")
    def test_git_askpass_env_set(self, mock_remove, mock_exists, mock_askpass, mock_run):
        git_clone(
            repo_url="https://github.com/owner/repo",
            token="tok",
            base_branch="main",
            work_dir="/tmp/work",
        )

        env = mock_run.call_args[1]["env"]
        assert env["GIT_ASKPASS"] == "/tmp/fake_askpass.sh"

    @patch("container.tools.git_clone.subprocess.run")
    @patch("container.tools.git_clone._create_askpass_script", return_value="/tmp/fake_askpass.sh")
    @patch("container.tools.git_clone.os.path.exists", return_value=True)
    @patch("container.tools.git_clone.os.remove")
    def test_askpass_script_cleaned_up(self, mock_remove, mock_exists, mock_askpass, mock_run):
        git_clone(
            repo_url="https://github.com/owner/repo",
            token="tok",
            base_branch="main",
            work_dir="/tmp/work",
        )

        assert mock_remove.call_count == 2
        removed_paths = [call[0][0] for call in mock_remove.call_args_list]
        assert "/tmp/fake_askpass.sh" in removed_paths
        assert "/tmp/fake_askpass.sh.token" in removed_paths

    @patch("container.tools.git_clone.subprocess.run")
    @patch("container.tools.git_clone._create_askpass_script", return_value="/tmp/fake_askpass.sh")
    @patch("container.tools.git_clone.os.path.exists", return_value=True)
    @patch("container.tools.git_clone.os.remove")
    def test_askpass_cleaned_up_on_error(self, mock_remove, mock_exists, mock_askpass, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")

        try:
            git_clone(
                repo_url="https://github.com/owner/repo",
                token="tok",
                base_branch="main",
                work_dir="/tmp/work",
            )
        except subprocess.CalledProcessError:
            pass

        assert mock_remove.call_count == 2
        removed_paths = [call[0][0] for call in mock_remove.call_args_list]
        assert "/tmp/fake_askpass.sh" in removed_paths
        assert "/tmp/fake_askpass.sh.token" in removed_paths


class TestGitCloneBasic:
    """Test basic shallow clone without sparse checkout."""

    @patch("container.tools.git_clone.subprocess.run")
    @patch("container.tools.git_clone._create_askpass_script", return_value="/tmp/fake_askpass.sh")
    @patch("container.tools.git_clone.os.path.exists", return_value=True)
    @patch("container.tools.git_clone.os.remove")
    def test_shallow_clone_uses_depth_1(self, mock_remove, mock_exists, mock_askpass, mock_run):
        git_clone(
            repo_url="https://github.com/owner/repo",
            token="ghp_test123",
            base_branch="main",
            work_dir="/tmp/work",
        )

        mock_run.assert_called_once_with(
            ["git", "clone", "--depth", "1", "-b", "main",
             "https://x-access-token@github.com/owner/repo", "/tmp/work"],
            check=True, capture_output=True, env=mock_run.call_args[1]["env"],
        )

    @patch("container.tools.git_clone.subprocess.run")
    @patch("container.tools.git_clone._create_askpass_script", return_value="/tmp/fake_askpass.sh")
    @patch("container.tools.git_clone.os.path.exists", return_value=True)
    @patch("container.tools.git_clone.os.remove")
    def test_uses_check_true(self, mock_remove, mock_exists, mock_askpass, mock_run):
        git_clone(
            repo_url="https://github.com/o/r",
            token="t",
            base_branch="main",
            work_dir="/w",
        )

        assert mock_run.call_args[1]["check"] is True

    @patch("container.tools.git_clone.subprocess.run")
    @patch("container.tools.git_clone._create_askpass_script", return_value="/tmp/fake_askpass.sh")
    @patch("container.tools.git_clone.os.path.exists", return_value=True)
    @patch("container.tools.git_clone.os.remove")
    def test_uses_capture_output(self, mock_remove, mock_exists, mock_askpass, mock_run):
        git_clone(
            repo_url="https://github.com/o/r",
            token="t",
            base_branch="main",
            work_dir="/w",
        )

        assert mock_run.call_args[1]["capture_output"] is True

    @patch("container.tools.git_clone.subprocess.run")
    @patch("container.tools.git_clone._create_askpass_script", return_value="/tmp/fake_askpass.sh")
    @patch("container.tools.git_clone.os.path.exists", return_value=True)
    @patch("container.tools.git_clone.os.remove")
    def test_propagates_subprocess_error(self, mock_remove, mock_exists, mock_askpass, mock_run):
        mock_run.side_effect = subprocess.CalledProcessError(128, "git")

        try:
            git_clone(
                repo_url="https://github.com/o/r",
                token="t",
                base_branch="main",
                work_dir="/w",
            )
            assert False, "Should have raised CalledProcessError"
        except subprocess.CalledProcessError:
            pass


class TestGitCloneSparseCheckout:
    """Test sparse checkout path."""

    @patch("container.tools.git_clone.subprocess.run")
    @patch("container.tools.git_clone._create_askpass_script", return_value="/tmp/fake_askpass.sh")
    @patch("container.tools.git_clone.os.path.exists", return_value=True)
    @patch("container.tools.git_clone.os.remove")
    def test_sparse_clone_runs_three_commands(self, mock_remove, mock_exists, mock_askpass, mock_run):
        git_clone(
            repo_url="https://github.com/owner/repo",
            token="tok",
            base_branch="main",
            work_dir="/tmp/work",
            sparse_paths=["src/", "lib/"],
        )

        assert mock_run.call_count == 3

    @patch("container.tools.git_clone.subprocess.run")
    @patch("container.tools.git_clone._create_askpass_script", return_value="/tmp/fake_askpass.sh")
    @patch("container.tools.git_clone.os.path.exists", return_value=True)
    @patch("container.tools.git_clone.os.remove")
    def test_sparse_clone_first_command_uses_filter_and_no_checkout(self, mock_remove, mock_exists, mock_askpass, mock_run):
        git_clone(
            repo_url="https://github.com/owner/repo",
            token="tok",
            base_branch="main",
            work_dir="/tmp/work",
            sparse_paths=["src/"],
        )

        first_call_args = mock_run.call_args_list[0][0][0]
        assert "--filter=blob:none" in first_call_args
        assert "--no-checkout" in first_call_args
        assert "--depth" in first_call_args

    @patch("container.tools.git_clone.subprocess.run")
    @patch("container.tools.git_clone._create_askpass_script", return_value="/tmp/fake_askpass.sh")
    @patch("container.tools.git_clone.os.path.exists", return_value=True)
    @patch("container.tools.git_clone.os.remove")
    def test_sparse_checkout_set_includes_paths(self, mock_remove, mock_exists, mock_askpass, mock_run):
        git_clone(
            repo_url="https://github.com/owner/repo",
            token="tok",
            base_branch="main",
            work_dir="/tmp/work",
            sparse_paths=["src/", "docs/"],
        )

        second_call = mock_run.call_args_list[1]
        args = second_call[0][0]
        assert args == ["git", "sparse-checkout", "set", "src/", "docs/"]
        assert second_call[1]["cwd"] == "/tmp/work"

    @patch("container.tools.git_clone.subprocess.run")
    @patch("container.tools.git_clone._create_askpass_script", return_value="/tmp/fake_askpass.sh")
    @patch("container.tools.git_clone.os.path.exists", return_value=True)
    @patch("container.tools.git_clone.os.remove")
    def test_sparse_checkout_final_command_is_checkout(self, mock_remove, mock_exists, mock_askpass, mock_run):
        git_clone(
            repo_url="https://github.com/owner/repo",
            token="tok",
            base_branch="main",
            work_dir="/tmp/work",
            sparse_paths=["src/"],
        )

        third_call = mock_run.call_args_list[2]
        assert third_call[0][0] == ["git", "checkout"]
        assert third_call[1]["cwd"] == "/tmp/work"

    @patch("container.tools.git_clone.subprocess.run")
    @patch("container.tools.git_clone._create_askpass_script", return_value="/tmp/fake_askpass.sh")
    @patch("container.tools.git_clone.os.path.exists", return_value=True)
    @patch("container.tools.git_clone.os.remove")
    def test_no_sparse_when_paths_is_none(self, mock_remove, mock_exists, mock_askpass, mock_run):
        git_clone(
            repo_url="https://github.com/owner/repo",
            token="tok",
            base_branch="main",
            work_dir="/tmp/work",
            sparse_paths=None,
        )

        assert mock_run.call_count == 1
        args = mock_run.call_args[0][0]
        assert "--filter=blob:none" not in args
        assert "--no-checkout" not in args

    @patch("container.tools.git_clone.subprocess.run")
    @patch("container.tools.git_clone._create_askpass_script", return_value="/tmp/fake_askpass.sh")
    @patch("container.tools.git_clone.os.path.exists", return_value=True)
    @patch("container.tools.git_clone.os.remove")
    def test_sparse_all_commands_get_askpass_env(self, mock_remove, mock_exists, mock_askpass, mock_run):
        git_clone(
            repo_url="https://github.com/owner/repo",
            token="tok",
            base_branch="main",
            work_dir="/tmp/work",
            sparse_paths=["src/"],
        )

        for call_obj in mock_run.call_args_list:
            env = call_obj[1]["env"]
            assert "GIT_ASKPASS" in env

    @patch("container.tools.git_clone.subprocess.run")
    @patch("container.tools.git_clone._create_askpass_script", return_value="/tmp/fake_askpass.sh")
    @patch("container.tools.git_clone.os.path.exists", return_value=True)
    @patch("container.tools.git_clone.os.remove")
    def test_sparse_token_not_in_any_command_args(self, mock_remove, mock_exists, mock_askpass, mock_run):
        token = "ghp_supersecret123"
        git_clone(
            repo_url="https://github.com/owner/repo",
            token=token,
            base_branch="main",
            work_dir="/tmp/work",
            sparse_paths=["src/"],
        )

        for call_obj in mock_run.call_args_list:
            for arg in call_obj[0][0]:
                assert token not in arg
