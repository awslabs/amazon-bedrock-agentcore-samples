# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import TypedDict, Union
import boto3
from botocore.exceptions import ClientError
import json
import os

REGION = os.environ.get("AWS_REGION", "us-east-1")
WORKLOAD_NAME = os.environ.get("WORKLOAD_NAME", "opencode_runtime")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-agentcore", region_name=REGION)
    return _client


class GitCredentialResult(TypedDict):
    token: str


class GitCredentialAuthRequired(TypedDict):
    authorization_required: bool
    auth_url: str


CredentialResult = Union[GitCredentialResult, GitCredentialAuthRequired]


def resolve_git_credential(
    user_id: str,
    repo_url: str,
    workload_access_token: str = "",
) -> CredentialResult:
    """Resolve git credentials via AgentCore Identity SDK (3LO OAuth).

    Maps git host domain to credential provider name, calls
    GetResourceOauth2Token, and returns the access token or an
    authorization_required flag with the auth URL for elicitation.
    """
    client = _get_client()

    token = workload_access_token
    if not token:
        resp = client.get_workload_access_token_for_user_id(
            workloadName=WORKLOAD_NAME, userId=user_id
        )
        token = resp["workloadAccessToken"]

    from urllib.parse import urlparse
    domain = urlparse(repo_url).hostname or "github.com"
    provider_name = "github-provider" if domain == "github.com" else f"custom-{domain}"

    params = {
        "workloadIdentityToken": token,
        "resourceCredentialProviderName": provider_name,
        "oauth2Flow": "USER_FEDERATION",
        "scopes": ["repo"],
    }

    callback_url = os.environ.get("OAUTH_CALLBACK_URL", "")
    if callback_url:
        params["resourceOauth2ReturnUrl"] = callback_url
        params["customState"] = json.dumps({"user_id": user_id})

    # Check if the typed AuthorizationUrlException exists in this SDK version.
    # In some regions/SDK versions, it's not registered on the exceptions factory,
    # and accessing it raises AttributeError at except-clause resolution time
    # (which propagates out of the try/except entirely).
    _has_auth_url_exc = hasattr(client.exceptions, "AuthorizationUrlException")

    try:
        resp = client.get_resource_oauth2_token(**params)
        if resp.get("authorizationUrl"):
            return {"authorization_required": True, "auth_url": resp["authorizationUrl"]}
        return {"token": resp["accessToken"]}
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code == "AuthorizationUrlException":
            auth_url = exc.response.get("AuthorizationUrl", "")
            return {"authorization_required": True, "auth_url": auth_url}
        if code == "ResourceNotFoundException":
            raise RuntimeError(
                f"No credential provider registered for the git host derived "
                f"from '{repo_url}'. Run 'connect_git_host' first, or ask your "
                f"administrator to register a credential provider."
            ) from exc
        raise
    except Exception as exc:
        # Handle the typed AuthorizationUrlException if the SDK has it.
        if _has_auth_url_exc and isinstance(exc, client.exceptions.AuthorizationUrlException):
            return {"authorization_required": True, "auth_url": getattr(exc, "authorization_url", "")}
        raise
