# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""OpenCode VPC stack — VPC, subnets, NAT Gateway, VPC endpoints.

Requirements: 8, 10.1
- Private subnets with no direct internet access; NAT Gateway for outbound
- S3 + DynamoDB gateway endpoints (free)
- Interface endpoints for all services called from within the VPC:
  ECR, CloudWatch Logs, CloudWatch Monitoring, KMS, STS,
  Secrets Manager, Lambda, Bedrock, Bedrock AgentCore, X-Ray
"""

import aws_cdk as cdk
from aws_cdk import (
    aws_ec2 as ec2,
    aws_iam as iam,
    aws_kms as kms,
    aws_logs as logs,
    RemovalPolicy,
)
import cdk_nag
from constructs import Construct

from stacks import retention_days


class VpcStack(cdk.Stack):
    """VPC with public/private subnets, NAT GW, VPC endpoints for all services."""

    def __init__(self, scope: Construct, construct_id: str, *, cmk: kms.IKey, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        log_retention = self.node.try_get_context("cloudwatch_log_retention_days") or 90

        # -----------------------------------------------------------------
        # VPC (10.0.0.0/16) — 2 AZs, public + private subnets
        # -----------------------------------------------------------------
        availability_zones = self.node.try_get_context("availability_zones")

        vpc_kwargs: dict = {
            "ip_addresses": ec2.IpAddresses.cidr("10.0.0.0/16"),
            "nat_gateways": 1,
            "subnet_configuration": [
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24,
                ),
            ],
        }

        if availability_zones:
            vpc_kwargs["availability_zones"] = availability_zones
        else:
            vpc_kwargs["max_azs"] = 2

        self.vpc = ec2.Vpc(self, "Vpc", **vpc_kwargs)

        # -----------------------------------------------------------------
        # VPC Flow Logs
        # -----------------------------------------------------------------
        flow_log_group = logs.LogGroup(
            self,
            "VpcFlowLogGroup",
            retention=retention_days(log_retention),
            removal_policy=RemovalPolicy.RETAIN,
            encryption_key=cmk,
        )
        flow_log_role = iam.Role(
            self,
            "VpcFlowLogRole",
            assumed_by=iam.ServicePrincipal("vpc-flow-logs.amazonaws.com"),
        )
        self.vpc.add_flow_log(
            "FlowLog",
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(
                flow_log_group, flow_log_role
            ),
            traffic_type=ec2.FlowLogTrafficType.ALL,
        )

        # -----------------------------------------------------------------
        # VPC Endpoint Security Group (for interface endpoints)
        # -----------------------------------------------------------------
        self.vpce_sg = ec2.SecurityGroup(
            self,
            "VpceSecurityGroup",
            vpc=self.vpc,
            description="VPC Endpoint interface security group",
            allow_all_outbound=False,
        )
        self.vpce_sg.add_ingress_rule(
            peer=ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            connection=ec2.Port.tcp(443),
            description="HTTPS from VPC CIDR",
        )

        # -----------------------------------------------------------------
        # Gateway Endpoints (S3, DynamoDB) — free
        # -----------------------------------------------------------------
        private_subnets = ec2.SubnetSelection(
            subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
        )

        self.vpc.add_gateway_endpoint(
            "S3Endpoint",
            service=ec2.GatewayVpcEndpointAwsService.S3,
            subnets=[private_subnets],
        )
        self.vpc.add_gateway_endpoint(
            "DynamoDbEndpoint",
            service=ec2.GatewayVpcEndpointAwsService.DYNAMODB,
            subnets=[private_subnets],
        )

        # -----------------------------------------------------------------
        # Interface Endpoints — all services called from within the VPC
        # -----------------------------------------------------------------
        interface_endpoints: dict[str, ec2.InterfaceVpcEndpointAwsService] = {
            # ECR — container image pulls
            "EcrApi": ec2.InterfaceVpcEndpointAwsService.ECR,
            "EcrDkr": ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER,
            # CloudWatch Logs — all in-VPC resources emit logs
            "CwLogs": ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
            # CloudWatch Monitoring — metrics from containers
            "CwMonitoring": ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_MONITORING,
            # KMS — CMK encrypt/decrypt for S3, DynamoDB, Secrets Manager
            "Kms": ec2.InterfaceVpcEndpointAwsService.KMS,
            # STS — AgentCore per-task scoped credential assumption
            "Sts": ec2.InterfaceVpcEndpointAwsService.STS,
            # Secrets Manager — Identity token vault (OAuth tokens)
            "SecretsManager": ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
            # Lambda — Lambda API calls from AgentCore runtime
            "Lambda": ec2.InterfaceVpcEndpointAwsService.LAMBDA_,
            # Bedrock — InvokeModel / InvokeModelWithResponseStream
            "Bedrock": ec2.InterfaceVpcEndpointAwsService.BEDROCK_RUNTIME,
            # X-Ray — distributed tracing from AgentCore containers
            "XRay": ec2.InterfaceVpcEndpointAwsService.XRAY,
        }

        for name, service in interface_endpoints.items():
            self.vpc.add_interface_endpoint(
                f"{name}Endpoint",
                service=service,
                subnets=private_subnets,
                security_groups=[self.vpce_sg],
                private_dns_enabled=True,
            )

        # Bedrock AgentCore — InvokeAgentRuntime, Identity SDK
        # Not in the standard InterfaceVpcEndpointAwsService enum;
        # use the service name directly.
        self.vpc.add_interface_endpoint(
            "BedrockAgentCoreEndpoint",
            service=ec2.InterfaceVpcEndpointService(
                f"com.amazonaws.{self.region}.bedrock-agentcore",
                port=443,
            ),
            subnets=private_subnets,
            security_groups=[self.vpce_sg],
            private_dns_enabled=True,
        )

        # -----------------------------------------------------------------
        # cdk-nag suppressions
        # -----------------------------------------------------------------
        cdk_nag.NagSuppressions.add_resource_suppressions(
            self.vpce_sg,
            [
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-EC23",
                    reason=(
                        "Ingress uses VPC CIDR (10.0.0.0/16) which resolves via "
                        "Fn::GetAtt at deploy time; not open to 0.0.0.0/0."
                    ),
                ),
                cdk_nag.NagPackSuppression(
                    id="CdkNagValidationFailure",
                    reason=(
                        "Security group rule uses Fn::GetAtt for VPC CIDR "
                        "which cannot be validated at synth time."
                    ),
                ),
            ],
        )

        cdk_nag.NagSuppressions.add_resource_suppressions(
            flow_log_role,
            [
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason="VPC Flow Log role needs logs:CreateLogStream and logs:PutLogEvents with wildcard on log stream.",
                ),
            ],
            apply_to_children=True,
        )
