# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for VPC stack (stacks/vpc_stack.py).

Validates: Requirements 10.1, 10.2
- VPC endpoints for AWS service traffic (no direct internet for service calls)
- NAT Gateway for outbound HTTPS
"""

import json
from pathlib import Path

import aws_cdk as cdk
from aws_cdk import assertions
from aws_cdk import aws_kms as kms
import pytest

from stacks.vpc_stack import VpcStack

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CDK_JSON_PATH = Path(__file__).resolve().parents[2] / "cdk.json"


def _load_cdk_context() -> dict:
    with open(CDK_JSON_PATH) as f:
        return json.load(f)["context"]


def _build_vpc_template() -> assertions.Template:
    ctx = _load_cdk_context()
    app = cdk.App(context=ctx)
    env = cdk.Environment(account="123456789012", region="us-east-1")
    cmk_stack = cdk.Stack(app, "StubCmkStack", env=env)
    stub_cmk = kms.Key(cmk_stack, "StubCmk")
    stack = VpcStack(app, "TestVpc", cmk=stub_cmk, env=env)
    return assertions.Template.from_stack(stack)


# ---------------------------------------------------------------------------
# VPC Endpoint tests (Requirement 10.1)
# ---------------------------------------------------------------------------

class TestVpcEndpoints:
    """Verify VPC endpoints for AWS service traffic."""

    def test_s3_gateway_endpoint_exists(self):
        """S3 gateway endpoint exists (ServiceName uses Fn::Join intrinsic)."""
        template = _build_vpc_template()
        tpl = template.to_json()
        found = any(
            r["Type"] == "AWS::EC2::VPCEndpoint"
            and r["Properties"].get("VpcEndpointType") == "Gateway"
            and "S3" in lid
            for lid, r in tpl["Resources"].items()
        )
        assert found, "S3 gateway endpoint not found"

    def test_dynamodb_gateway_endpoint_exists(self):
        """DynamoDB gateway endpoint exists (ServiceName uses Fn::Join intrinsic)."""
        template = _build_vpc_template()
        tpl = template.to_json()
        found = any(
            r["Type"] == "AWS::EC2::VPCEndpoint"
            and r["Properties"].get("VpcEndpointType") == "Gateway"
            and "DynamoDb" in lid
            for lid, r in tpl["Resources"].items()
        )
        assert found, "DynamoDB gateway endpoint not found"

    def test_gateway_endpoint_count(self):
        """Exactly 2 gateway endpoints: S3 and DynamoDB."""
        template = _build_vpc_template()
        resources = template.find_resources(
            "AWS::EC2::VPCEndpoint",
            {"Properties": {"VpcEndpointType": "Gateway"}},
        )
        assert len(resources) == 2, (
            f"Expected 2 gateway endpoints (S3, DynamoDB), found {len(resources)}"
        )

    def test_interface_endpoint_count(self):
        """11 interface endpoints: ECR API, ECR DKR, CloudWatch Logs,
        CloudWatch Monitoring, KMS, STS, Secrets Manager, Lambda,
        Bedrock Runtime, X-Ray, Bedrock AgentCore."""
        template = _build_vpc_template()
        resources = template.find_resources(
            "AWS::EC2::VPCEndpoint",
            {"Properties": {"VpcEndpointType": "Interface"}},
        )
        assert len(resources) == 11, (
            f"Expected 11 interface endpoints, found {len(resources)}"
        )

    def test_total_vpc_endpoint_count(self):
        """13 total VPC endpoints (2 gateway + 11 interface)."""
        template = _build_vpc_template()
        resources = template.find_resources("AWS::EC2::VPCEndpoint")
        assert len(resources) == 13, (
            f"Expected 13 total VPC endpoints, found {len(resources)}"
        )

    def test_bedrock_runtime_endpoint_exists(self):
        template = _build_vpc_template()
        template.has_resource_properties(
            "AWS::EC2::VPCEndpoint",
            {
                "ServiceName": assertions.Match.string_like_regexp(
                    ".*bedrock-runtime$"
                ),
                "VpcEndpointType": "Interface",
            },
        )

    def test_secrets_manager_endpoint_exists(self):
        template = _build_vpc_template()
        template.has_resource_properties(
            "AWS::EC2::VPCEndpoint",
            {
                "ServiceName": assertions.Match.string_like_regexp(
                    ".*secretsmanager$"
                ),
                "VpcEndpointType": "Interface",
            },
        )

    def test_ecr_api_endpoint_exists(self):
        template = _build_vpc_template()
        template.has_resource_properties(
            "AWS::EC2::VPCEndpoint",
            {
                "ServiceName": assertions.Match.string_like_regexp(
                    ".*ecr\\.api$"
                ),
                "VpcEndpointType": "Interface",
            },
        )

    def test_ecr_dkr_endpoint_exists(self):
        template = _build_vpc_template()
        template.has_resource_properties(
            "AWS::EC2::VPCEndpoint",
            {
                "ServiceName": assertions.Match.string_like_regexp(
                    ".*ecr\\.dkr$"
                ),
                "VpcEndpointType": "Interface",
            },
        )

    def test_sts_endpoint_exists(self):
        template = _build_vpc_template()
        template.has_resource_properties(
            "AWS::EC2::VPCEndpoint",
            {
                "ServiceName": assertions.Match.string_like_regexp(".*sts$"),
                "VpcEndpointType": "Interface",
            },
        )

    def test_cloudwatch_logs_endpoint_exists(self):
        template = _build_vpc_template()
        template.has_resource_properties(
            "AWS::EC2::VPCEndpoint",
            {
                "ServiceName": assertions.Match.string_like_regexp(
                    ".*logs$"
                ),
                "VpcEndpointType": "Interface",
            },
        )

    def test_xray_endpoint_exists(self):
        template = _build_vpc_template()
        template.has_resource_properties(
            "AWS::EC2::VPCEndpoint",
            {
                "ServiceName": assertions.Match.string_like_regexp(
                    ".*xray$"
                ),
                "VpcEndpointType": "Interface",
            },
        )


# ---------------------------------------------------------------------------
# NAT Gateway tests (Requirement 10.2)
# ---------------------------------------------------------------------------

class TestNatGateway:
    """Verify NAT Gateway is in public subnets only."""

    def test_single_nat_gateway(self):
        template = _build_vpc_template()
        template.resource_count_is("AWS::EC2::NatGateway", 1)

    def test_nat_gateway_has_elastic_ip(self):
        template = _build_vpc_template()
        template.has_resource_properties(
            "AWS::EC2::NatGateway",
            {
                "AllocationId": assertions.Match.any_value(),
            },
        )

    def test_nat_gateway_in_public_subnet(self):
        """NAT Gateway must reference a public subnet."""
        template = _build_vpc_template()
        tpl = template.to_json()

        # Find the NAT Gateway resource
        nat_gw = None
        for logical_id, resource in tpl["Resources"].items():
            if resource["Type"] == "AWS::EC2::NatGateway":
                nat_gw = resource
                break
        assert nat_gw is not None, "NAT Gateway not found"

        # The NAT GW's SubnetId should reference a public subnet
        subnet_ref = nat_gw["Properties"]["SubnetId"]["Ref"]

        # Verify the referenced subnet is a public subnet (has MapPublicIpOnLaunch=true)
        subnet_resource = tpl["Resources"].get(subnet_ref)
        assert subnet_resource is not None, f"Subnet {subnet_ref} not found"
        assert subnet_resource["Type"] == "AWS::EC2::Subnet"
        assert subnet_resource["Properties"].get("MapPublicIpOnLaunch") is True, (
            "NAT Gateway is not in a public subnet"
        )


# ---------------------------------------------------------------------------
# VPC Flow Logs test
# ---------------------------------------------------------------------------

class TestVpcFlowLogs:
    """Verify VPC Flow Logs are configured."""

    def test_flow_log_exists(self):
        template = _build_vpc_template()
        template.resource_count_is("AWS::EC2::FlowLog", 1)

    def test_flow_log_captures_all_traffic(self):
        template = _build_vpc_template()
        template.has_resource_properties(
            "AWS::EC2::FlowLog",
            {"TrafficType": "ALL"},
        )
