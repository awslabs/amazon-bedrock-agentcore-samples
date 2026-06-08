# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for resolve_git_credential client caching.

Validates: Requirement 14.1, 14.2
Verifies that the boto3 client is created once and reused across invocations.
"""

import importlib
import sys
from unittest.mock import patch, MagicMock

# Stub strands before importing the module under test
strands_mock = MagicMock()
strands_mock.tool = lambda fn: fn  # @tool is identity decorator for testing
sys.modules.setdefault("strands", strands_mock)

# Import the actual module (not the re-exported function from __init__.py)
_mod = importlib.import_module("container.tools.resolve_git_credential")


class TestGetClientCaching:
    """Verify _get_client returns a cached singleton."""

    def setup_method(self):
        # Reset the module-level cache before each test
        _mod._client = None

    @patch("container.tools.resolve_git_credential.boto3.client")
    def test_get_client_creates_client_once(self, mock_boto3_client):
        mock_boto3_client.return_value = MagicMock()

        client1 = _mod._get_client()
        client2 = _mod._get_client()

        mock_boto3_client.assert_called_once()
        assert client1 is client2

    @patch("container.tools.resolve_git_credential.boto3.client")
    def test_get_client_passes_correct_service_and_region(self, mock_boto3_client):
        mock_boto3_client.return_value = MagicMock()

        _mod._get_client()

        mock_boto3_client.assert_called_once_with(
            "bedrock-agentcore", region_name=_mod.REGION
        )

    @patch("container.tools.resolve_git_credential.boto3.client")
    def test_get_client_returns_boto3_client_instance(self, mock_boto3_client):
        sentinel = MagicMock(name="sentinel-client")
        mock_boto3_client.return_value = sentinel

        result = _mod._get_client()

        assert result is sentinel


class TestResolveGitCredentialUsesCache:
    """Verify resolve_git_credential uses _get_client instead of creating a new client."""

    def setup_method(self):
        _mod._client = None

    @patch("container.tools.resolve_git_credential.boto3.client")
    def test_multiple_calls_create_client_once(self, mock_boto3_client):
        mock_client = MagicMock()
        mock_client.get_resource_oauth2_token.return_value = {
            "accessToken": "fake-token"
        }
        mock_boto3_client.return_value = mock_client

        _mod.resolve_git_credential(
            user_id="user1",
            repo_url="https://github.com/owner/repo",
            workload_access_token="wat-123",
        )
        _mod.resolve_git_credential(
            user_id="user2",
            repo_url="https://github.com/owner/repo2",
            workload_access_token="wat-456",
        )

        # boto3.client should only be called once despite two resolve calls
        mock_boto3_client.assert_called_once()

    @patch("container.tools.resolve_git_credential.boto3.client")
    def test_three_calls_still_one_client(self, mock_boto3_client):
        mock_client = MagicMock()
        mock_client.get_resource_oauth2_token.return_value = {
            "accessToken": "tok"
        }
        mock_boto3_client.return_value = mock_client

        for i in range(3):
            _mod.resolve_git_credential(
                user_id=f"user{i}",
                repo_url="https://github.com/o/r",
                workload_access_token="wat",
            )

        mock_boto3_client.assert_called_once()
