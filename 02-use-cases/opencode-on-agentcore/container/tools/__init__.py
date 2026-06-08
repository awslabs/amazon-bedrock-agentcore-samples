# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Shared tool implementations for the OpenCode container."""

from container.tools.resolve_git_credential import (
    resolve_git_credential,
    GitCredentialResult,
    GitCredentialAuthRequired,
    CredentialResult,
)
from container.tools.git_clone import git_clone
from container.tools.run_opencode_acp import (
    run_opencode_acp,
    run_opencode_acp_impl,
    OpenCodeResult,
)
from container.tools.scan_and_strip_credentials import (
    scan_and_strip_credentials,
    scan_and_strip_credentials_impl,
    scan_and_strip_content,
    ScanResult,
    PATTERNS,
    PLACEHOLDER,
)
from container.tools.git_push_and_create_pr import (
    git_push_and_create_pr,
    PushResult,
)

__all__ = [
    "resolve_git_credential",
    "GitCredentialResult",
    "GitCredentialAuthRequired",
    "CredentialResult",
    "git_clone",
    "run_opencode_acp",
    "run_opencode_acp_impl",
    "OpenCodeResult",
    "scan_and_strip_credentials",
    "scan_and_strip_credentials_impl",
    "scan_and_strip_content",
    "ScanResult",
    "PATTERNS",
    "PLACEHOLDER",
    "git_push_and_create_pr",
    "PushResult",
]
