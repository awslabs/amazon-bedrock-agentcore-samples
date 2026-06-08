#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""OpenCode on AgentCore — CDK Application entry point.

Architecture: User-scoped async coding service via AgentCore Gateway (MCP-only).
  AgentCore Gateway → AgentCore Runtime (OpenCode in Firecracker microVM)

Stacks:
  VPC, Security, JobStore, CallbackApi, AgentCore, Gateway, Policy, Identity, Observability
"""

import os

import aws_cdk as cdk
import cdk_nag

from stacks.vpc_stack import VpcStack
from stacks.security_stack import SecurityStack
from stacks.job_store_stack import JobStoreStack
from stacks.callback_api_stack import CallbackApiStack
from stacks.agentcore_stack import AgentCoreStack
from stacks.gateway_stack import GatewayStack
from stacks.policy_stack import PolicyStack
from stacks.identity_stack import IdentityStack
from stacks.observability_stack import ObservabilityStack
from stacks import apply_standard_tags

app = cdk.App()

_account = (
    app.node.try_get_context("account")
    or os.environ.get("CDK_DEFAULT_ACCOUNT")
    or os.environ.get("AWS_ACCOUNT_ID")
)
_region = (
    app.node.try_get_context("region")
    or os.environ.get("CDK_DEFAULT_REGION")
    or os.environ.get("AWS_REGION")
    or os.environ.get("AWS_DEFAULT_REGION")
)

env = cdk.Environment(account=_account, region=_region)

# ---------------------------------------------------------------------------
# Foundation stacks
# ---------------------------------------------------------------------------
security_stack = SecurityStack(app, "OpenCodeSecurity", env=env)

vpc_stack = VpcStack(app, "OpenCodeVpc", cmk=security_stack.cmk, env=env)
vpc_stack.add_dependency(security_stack)

# ---------------------------------------------------------------------------
# Data layer
# ---------------------------------------------------------------------------
job_store_stack = JobStoreStack(
    app,
    "OpenCodeJobStore",
    cmk=security_stack.cmk,
    env=env,
)
job_store_stack.add_dependency(security_stack)

# ---------------------------------------------------------------------------
# Callback API (OAuth callback HTTP API + Lambda)
# ---------------------------------------------------------------------------
callback_api_stack = CallbackApiStack(
    app,
    "OpenCodeCallbackApi",
    cmk=security_stack.cmk,
    env=env,
)
callback_api_stack.add_dependency(security_stack)

# ---------------------------------------------------------------------------
# AgentCore base
# ---------------------------------------------------------------------------
agentcore_stack = AgentCoreStack(
    app,
    "OpenCodeAgentCore",
    vpc=vpc_stack.vpc,
    cmk=security_stack.cmk,
    callback_url=callback_api_stack.callback_url_value,
    env=env,
)
agentcore_stack.add_dependency(vpc_stack)
agentcore_stack.add_dependency(security_stack)
agentcore_stack.add_dependency(callback_api_stack)

# ---------------------------------------------------------------------------
# Identity (credential providers) — must be before Gateway
# ---------------------------------------------------------------------------
identity_stack = IdentityStack(
    app,
    "OpenCodeIdentity",
    cmk=security_stack.cmk,
    callback_url=callback_api_stack.callback_url_value,
    env=env,
)
identity_stack.add_dependency(security_stack)
identity_stack.add_dependency(callback_api_stack)

# ---------------------------------------------------------------------------
# Policy (Cedar) — must be before Gateway so the Gateway can reference the
# PolicyEngine ARN in its CloudFormation PolicyEngineConfiguration.
# ---------------------------------------------------------------------------
policy_stack = PolicyStack(
    app,
    "OpenCodePolicy",
    env=env,
)
policy_stack.add_dependency(security_stack)

# ---------------------------------------------------------------------------
# Gateway (sole client entry point)
# ---------------------------------------------------------------------------
gateway_stack = GatewayStack(
    app,
    "OpenCodeGateway",
    cognito_user_pool=security_stack.user_pool,
    cognito_client_id=security_stack.user_pool_client.user_pool_client_id,
    opencode_runtime=agentcore_stack.runtime,
    policy_engine_arn=policy_stack.policy_engine.attr_policy_engine_arn,
    cmk=security_stack.cmk,
    env=env,
)
gateway_stack.add_dependency(security_stack)
gateway_stack.add_dependency(agentcore_stack)
gateway_stack.add_dependency(policy_stack)

# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------
observability_stack = ObservabilityStack(
    app,
    "OpenCodeObservability",
    cmk=security_stack.cmk,
    env=env,
)
observability_stack.add_dependency(security_stack)

# ---------------------------------------------------------------------------
# Standard tags and cdk-nag
# ---------------------------------------------------------------------------
apply_standard_tags(app)
cdk.Aspects.of(app).add(cdk_nag.AwsSolutionsChecks(verbose=True))

app.synth()
