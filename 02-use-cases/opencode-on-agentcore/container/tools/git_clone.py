# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
import os
import subprocess
from typing import Optional

from container.lib.git_askpass import _create_askpass_script

# Re-exported so existing tests can patch ``container.tools.git_clone.
# _create_askpass_script`` directly.
__all__ = ["git_clone", "_create_askpass_script"]


def git_clone(
    repo_url: str,
    token: str,
    base_branch: str,
    work_dir: str,
    sparse_paths: Optional[list[str]] = None,
) -> None:
    """Clone a git repository with optional sparse checkout."""
    # Build clone URL with username only — no token in the URL
    clone_url = repo_url.replace("https://", "https://x-access-token@")

    askpass_path = _create_askpass_script(token)
    try:
        env = {**os.environ, "GIT_ASKPASS": askpass_path}

        if sparse_paths:
            subprocess.run(
                ["git", "clone", "--filter=blob:none", "--no-checkout",
                 "--depth", "1", "-b", base_branch, clone_url, work_dir],
                check=True, capture_output=True, env=env,
            )
            subprocess.run(
                ["git", "sparse-checkout", "set", *sparse_paths],
                cwd=work_dir, check=True, capture_output=True, env=env,
            )
            subprocess.run(
                ["git", "checkout"],
                cwd=work_dir, check=True, capture_output=True, env=env,
            )
        else:
            subprocess.run(
                ["git", "clone", "--depth", "1", "-b", base_branch, clone_url, work_dir],
                check=True, capture_output=True, env=env,
            )
    finally:
        if os.path.exists(askpass_path + ".token"):
            os.remove(askpass_path + ".token")
        if os.path.exists(askpass_path):
            os.remove(askpass_path)
