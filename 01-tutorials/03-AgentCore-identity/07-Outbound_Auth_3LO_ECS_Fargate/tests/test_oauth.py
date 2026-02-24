# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0
"""Tests for OAuth callback API."""

from unittest.mock import patch

from jwt.exceptions import PyJWTError

from tests.conftest import make_oidc_jwt, mock_bedrock_api_call


class TestHealthEndpoints:
    def test_ping(self, oauth_client):
        response = oauth_client.get("/ping")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestOAuthCallbackEndpoint:
    def test_callback_success(self, oauth_client):
        with (
            patch("backend.shared.alb_auth.verify_alb_jwt") as mock_verify,
            patch("botocore.client.BaseClient._make_api_call", new=mock_bedrock_api_call),
        ):
            mock_verify.return_value = {
                "sub": "test-user-id",
                "email": "test@example.com",
            }
            response = oauth_client.get(
                "/oauth2/callback",
                params={"session_id": "test-session-id"},
                headers={"x-amzn-oidc-data": make_oidc_jwt()},
            )

        assert response.status_code == 200
        assert "OAuth2 3LO Flow Completed Successfully" in response.text

    def test_callback_invalid_jwt(self, oauth_client):
        with patch("backend.shared.alb_auth.verify_alb_jwt") as mock_verify:
            mock_verify.side_effect = PyJWTError("Invalid token")
            response = oauth_client.get(
                "/oauth2/callback",
                params={"session_id": "test-session-id"},
                headers={"x-amzn-oidc-data": "invalid-jwt"},
            )

        assert response.status_code == 401
        assert "Invalid ALB token" in response.json()["detail"]

    def test_callback_missing_header(self, oauth_client):
        response = oauth_client.get(
            "/oauth2/callback",
            params={"session_id": "test-session-id"},
        )
        assert response.status_code == 422

    def test_callback_missing_session_id(self, oauth_client):
        with patch("backend.shared.alb_auth.verify_alb_jwt") as mock_verify:
            mock_verify.return_value = {
                "sub": "test-user-id",
                "email": "test@example.com",
            }
            response = oauth_client.get(
                "/oauth2/callback",
                headers={"x-amzn-oidc-data": make_oidc_jwt()},
            )
        assert response.status_code == 422
