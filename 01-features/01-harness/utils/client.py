"""boto3 client helpers for AgentCore Harness tutorials."""

import os
import boto3

REGION = os.environ.get("AWS_DEFAULT_REGION")

# Endpoint overrides (for non-production stages)
_CP_ENDPOINT = os.environ.get("BEDROCK_AGENTCORE_CP_ENDPOINT")
_DP_ENDPOINT = os.environ.get("BEDROCK_AGENTCORE_DP_ENDPOINT")


def _make_session():
    """Create a boto3 session."""
    return boto3.Session(region_name=REGION)


def get_agentcore_client(config=None):
    """Return a boto3 client for the Harness data plane (invoke, ExecuteCommand).

    Args:
        config: Optional botocore.config.Config (e.g. Config(read_timeout=300)).
    """
    kwargs = {}
    if _DP_ENDPOINT:
        kwargs["endpoint_url"] = _DP_ENDPOINT
    if config is not None:
        kwargs["config"] = config
    return _make_session().client("bedrock-agentcore", **kwargs)


def get_agentcore_control_client():
    """Return a boto3 client for the Harness control plane (create, get, update, delete)."""
    kwargs = {}
    if _CP_ENDPOINT:
        kwargs["endpoint_url"] = _CP_ENDPOINT
    return _make_session().client("bedrock-agentcore-control", **kwargs)
