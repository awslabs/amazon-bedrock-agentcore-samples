# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the unified FastMCP server and CDK stack.

Validates:
- All 6 MCP tools registered in the unified server
- GatewayStack accepts opencode_runtime parameter
- AgentCoreStack execution role includes StopRuntimeSession
"""

from __future__ import annotations

import json
from pathlib import Path

import aws_cdk as cdk
from aws_cdk import assertions
import pytest

from stacks.vpc_stack import VpcStack
from stacks.security_stack import SecurityStack
from stacks.agentcore_stack import AgentCoreStack
from stacks.gateway_stack import GatewayStack

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CDK_JSON_PATH = Path(__file__).resolve().parents[2] / "cdk.json"


def _load_cdk_context() -> dict:
    with open(CDK_JSON_PATH) as f:
        return json.load(f)["context"]


def _build_agentcore_template() -> assertions.Template:
    ctx = _load_cdk_context()
    app = cdk.App(context=ctx)
    env = cdk.Environment(account="123456789012", region="us-east-1")
    security_stack = SecurityStack(app, "TestSecurity", env=env)
    vpc_stack = VpcStack(app, "TestVpc", cmk=security_stack.cmk, env=env)
    stack = AgentCoreStack(
        app, "TestAgentCore", vpc=vpc_stack.vpc, cmk=security_stack.cmk,
        callback_url="https://test.execute-api.us-east-1.amazonaws.com/callback",
        env=env,
    )
    return assertions.Template.from_stack(stack)


def _build_gateway_template() -> assertions.Template:
    ctx = _load_cdk_context()
    app = cdk.App(context=ctx)
    env = cdk.Environment(account="123456789012", region="us-east-1")
    security_stack = SecurityStack(app, "TestSecurity", env=env)
    vpc_stack = VpcStack(app, "TestVpc", cmk=security_stack.cmk, env=env)
    agentcore_stack = AgentCoreStack(
        app, "TestAgentCore", vpc=vpc_stack.vpc, cmk=security_stack.cmk,
        callback_url="https://test.execute-api.us-east-1.amazonaws.com/callback",
        env=env,
    )
    stub_policy_engine_arn = (
        "arn:aws:bedrock-agentcore:us-east-1:123456789012:policy-engine/STUB000001"
    )
    stack = GatewayStack(
        app,
        "TestGateway",
        cognito_user_pool=security_stack.user_pool,
        cognito_client_id=security_stack.user_pool_client.user_pool_client_id,
        opencode_runtime=agentcore_stack.runtime,
        policy_engine_arn=stub_policy_engine_arn,
        cmk=security_stack.cmk,
        env=env,
    )
    return assertions.Template.from_stack(stack)


def _collect_all_policy_actions(tpl: dict) -> set[str]:
    actions: set[str] = set()
    for lid, res in tpl["Resources"].items():
        if res["Type"] == "AWS::IAM::Policy":
            doc = res.get("Properties", {}).get("PolicyDocument", {})
            for stmt in doc.get("Statement", []):
                act = stmt.get("Action", [])
                if isinstance(act, str):
                    actions.add(act)
                elif isinstance(act, list):
                    actions.update(act)
    return actions


def _collect_resources_for_action(tpl: dict, action: str) -> list:
    resources: list = []
    for lid, res in tpl["Resources"].items():
        if res["Type"] == "AWS::IAM::Policy":
            doc = res.get("Properties", {}).get("PolicyDocument", {})
            for stmt in doc.get("Statement", []):
                act = stmt.get("Action", [])
                if isinstance(act, str):
                    act = [act]
                if action in act:
                    resource = stmt.get("Resource", [])
                    if isinstance(resource, list):
                        resources.extend(resource)
                    else:
                        resources.append(resource)
    return resources


# ---------------------------------------------------------------------------
# 1. Unified FastMCP server — tool registration (Req 1.1, 1.6, 9.3)
# ---------------------------------------------------------------------------


class TestUnifiedServerToolRegistration:
    """Verify the unified FastMCP server registers all 6 tools."""

    EXPECTED_TOOLS = {
        "code",
        "run_coding_task",
        "connect_git_host",
        "get_task_status",
        "list_tasks",
        "cancel_task",
    }

    def test_server_registers_exactly_6_tools(self):
        """FastMCP server has exactly 6 callable tool functions.

        Validates: Requirement 1.1
        """
        import container.code_mcp_server as mod

        actual = {
            name
            for name in self.EXPECTED_TOOLS
            if hasattr(mod, name) and callable(getattr(mod, name))
        }
        assert actual == self.EXPECTED_TOOLS, (
            f"Expected {self.EXPECTED_TOOLS}, found {actual}"
        )

    def test_server_name_is_opencode(self):
        """FastMCP server is named 'opencode'.

        Validates: Requirements 1.6, 9.3
        """
        import container.code_mcp_server as mod

        # The mcp object is created via FastMCP("opencode")
        # In the test env, FastMCP is mocked, so we check the source
        source = Path("container/code_mcp_server.py").read_text()
        assert 'FastMCP("opencode")' in source, (
            "FastMCP server should be named 'opencode'"
        )

    def test_no_extra_tools_beyond_expected(self):
        """No unexpected tool functions registered beyond the 6.

        Validates: Requirement 1.1
        """
        source = Path("container/code_mcp_server.py").read_text()
        # Count @mcp.tool() decorators
        tool_decorator_count = source.count("@mcp.tool()")
        assert tool_decorator_count == 6, (
            f"Expected 6 @mcp.tool() decorators, found {tool_decorator_count}"
        )


# ---------------------------------------------------------------------------
# 2. GatewayStack accepts opencode_runtime parameter
# ---------------------------------------------------------------------------


class TestGatewaySingleRuntime:
    """Verify GatewayStack accepts the opencode_runtime parameter."""

    def test_gateway_constructor_has_opencode_runtime_param(self):
        """GatewayStack.__init__ accepts opencode_runtime."""
        import inspect

        sig = inspect.signature(GatewayStack.__init__)
        param_names = set(sig.parameters.keys())
        assert "opencode_runtime" in param_names

    def test_gateway_iam_policy_references_one_runtime_arn(self):
        """Gateway IAM policy references the opencode runtime ARN."""
        template = _build_gateway_template()
        tpl = template.to_json()
        resources = _collect_resources_for_action(
            tpl, "bedrock-agentcore:InvokeAgentRuntime"
        )
        runtime_arns = [
            str(r)
            for r in resources
            if "runtime" in str(r).lower() and "gateway" not in str(r).lower()
        ]
        assert len(runtime_arns) > 0, "No runtime ARN references found in Gateway IAM policy"


# ---------------------------------------------------------------------------
# 3. AgentCoreStack execution role — StopRuntimeSession
# ---------------------------------------------------------------------------


class TestAgentCoreStopRuntimeSession:
    """Verify AgentCoreStack execution role includes StopRuntimeSession."""

    def test_execution_role_has_stop_runtime_session(self):
        """Execution role includes bedrock-agentcore:StopRuntimeSession.

        Validates: Requirement 5.1
        """
        template = _build_agentcore_template()
        tpl = template.to_json()
        actions = _collect_all_policy_actions(tpl)
        assert "bedrock-agentcore:StopRuntimeSession" in actions, (
            "AgentCoreStack execution role missing StopRuntimeSession permission"
        )

    def test_stop_runtime_session_scoped_to_agentcore_resources(self):
        """StopRuntimeSession is scoped to bedrock-agentcore resources.

        Validates: Requirement 5.1
        """
        template = _build_agentcore_template()
        tpl = template.to_json()
        resources = _collect_resources_for_action(
            tpl, "bedrock-agentcore:StopRuntimeSession"
        )
        assert len(resources) > 0, "No resources found for StopRuntimeSession"
        assert any("bedrock-agentcore" in str(r) for r in resources), (
            "StopRuntimeSession not scoped to bedrock-agentcore resources"
        )
