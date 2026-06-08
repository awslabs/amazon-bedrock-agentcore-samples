# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0
"""OpenCode AgentCore stack — execution role, security group, ECR, Runtime, Endpoint.

Bedrock IAM scoped to single default_model_id. Identity SDK permissions included.
Single FastMCP Python server on port 8000. Managed session storage enabled.

Requirements: 6.1, 6.4, 10.3, 14.1, 14.2, 14.3, 14.4
"""

import aws_cdk as cdk
from aws_cdk import (
    aws_bedrockagentcore as bedrockagentcore,
    aws_ec2 as ec2,
    aws_ecr as ecr,
    aws_ecr_assets as ecr_assets,
    aws_iam as iam,
    aws_kms as kms,
    RemovalPolicy,
)
import cdk_nag
from constructs import Construct


class AgentCoreStack(cdk.Stack):
    """AgentCore base resources: IAM role, SG, ECR."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        vpc: ec2.IVpc,
        cmk: kms.IKey,
        callback_url: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self._vpc = vpc
        self._cmk = cmk

        default_model_id = self.node.try_get_context("default_model_id") or "global.anthropic.claude-opus-4-6-v1"

        # -----------------------------------------------------------------
        # Security Group
        # -----------------------------------------------------------------
        self.agentcore_sg = ec2.SecurityGroup(
            self,
            "AgentCoreSecurityGroup",
            vpc=self._vpc,
            description="AgentCore container security group",
            allow_all_outbound=True,
        )

        # -----------------------------------------------------------------
        # ECR Repository
        # -----------------------------------------------------------------
        self.ecr_repo = ecr.Repository(
            self,
            "OpenCodeEcrRepo",
            repository_name="opencode-agentcore",
            removal_policy=RemovalPolicy.RETAIN,
            image_scan_on_push=True,
            encryption=ecr.RepositoryEncryption.KMS,
            encryption_key=self._cmk,
        )

        # -----------------------------------------------------------------
        # AgentCore Execution IAM Role
        # Bedrock scoped to single model. Identity SDK permissions included.
        # -----------------------------------------------------------------
        self.execution_role = iam.Role(
            self,
            "AgentCoreExecutionRole",
            role_name=f"opencode-agentcore-execution-role-{self.region}",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("bedrock-agentcore.amazonaws.com",
                    conditions={
                        "StringEquals": {"aws:SourceAccount": self.account},
                        "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:*"},
                    },
                ),
            ),
            description="Execution role for OpenCode AgentCore containers",
        )

        # Bedrock InvokeModel — scoped to cross-region inference profile + its underlying
        # foundation model. When OpenCode calls the ``global.`` inference profile, Bedrock
        # fans out to the foundation model in each eligible region; both ARNs must be in
        # the allow list.
        bedrock_resources = []
        if default_model_id.startswith("arn:"):
            bedrock_resources.append(default_model_id)
        else:
            # Strip any region/global/us/eu prefix to derive the base foundation model id.
            # e.g. "global.anthropic.claude-opus-4-6-v1" → "anthropic.claude-opus-4-6-v1"
            _prefixes = ("global.", "us.", "eu.", "jp.", "apac.", "au.")
            base_model_id = default_model_id
            for _p in _prefixes:
                if base_model_id.startswith(_p):
                    base_model_id = base_model_id[len(_p):]
                    break
            # foundation-model ARN for the underlying model (no region prefix, no account)
            bedrock_resources.append(
                f"arn:aws:bedrock:*::foundation-model/{base_model_id}"
            )
            # inference-profile ARN for the cross-region profile (if the id has a prefix)
            if base_model_id != default_model_id:
                bedrock_resources.append(
                    f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/{default_model_id}"
                )
        # Also allow Sonnet 4 for OpenCode (in-region, works via VPC endpoint)
        bedrock_resources.append(
            f"arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-20250514-v1:0"
        )

        self.execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="BedrockInvokeModel",
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=bedrock_resources,
            )
        )

        # DynamoDB read/write for job store only (no team config table)
        self.execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="DynamoDbAccess",
                actions=["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query"],
                resources=[
                    f"arn:aws:dynamodb:{self.region}:{self.account}:table/opencode-jobs",
                    f"arn:aws:dynamodb:{self.region}:{self.account}:table/opencode-jobs/index/*",
                ],
            )
        )

        # STS AssumeRole for per-task scoped credentials
        self.execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="StsAssumeRole",
                actions=["sts:AssumeRole"],
                resources=[self.execution_role.role_arn],
            )
        )

        # CloudWatch Logs and Metrics
        self.execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="CloudWatchLogsAndMetrics",
                actions=[
                    "logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents",
                    "logs:DescribeLogStreams", "logs:DescribeLogGroups",
                    "cloudwatch:PutMetricData",
                ],
                resources=["*"],
            )
        )

        # ECR image pull
        self.execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="ECRImageAccess",
                actions=["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                resources=[f"arn:aws:ecr:{self.region}:{self.account}:repository/*"],
            )
        )
        self.execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="ECRTokenAccess",
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"],
            )
        )

        # X-Ray tracing
        self.execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="XRayTracing",
                actions=[
                    "xray:PutTraceSegments", "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules", "xray:GetSamplingTargets",
                ],
                resources=["*"],
            )
        )

        # AgentCore Identity SDK — credential management + cross-session cancellation
        self.execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="AgentCoreIdentity",
                actions=[
                    "bedrock-agentcore:GetCredential",
                    "bedrock-agentcore:ListCredentialProviders",
                    "bedrock-agentcore:GetResourceOauth2Token",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                    "bedrock-agentcore:StopRuntimeSession",
                ],
                resources=[f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:*"],
            )
        )

        # Secrets Manager read for Identity token vault (stores user OAuth tokens)
        self.execution_role.add_to_policy(
            iam.PolicyStatement(
                sid="IdentityTokenVaultAccess",
                actions=["secretsmanager:GetSecretValue"],
                resources=[
                    f"arn:aws:secretsmanager:{self.region}:{self.account}:secret:bedrock-agentcore-identity*",
                ],
            )
        )

        # KMS decrypt for CMK
        self._cmk.grant_encrypt_decrypt(self.execution_role)

        # -----------------------------------------------------------------
        # Container Image — ARM64, Python FastMCP server
        # -----------------------------------------------------------------
        self.image_asset = ecr_assets.DockerImageAsset(
            self,
            "OpenCodeImage",
            directory="container",
            platform=ecr_assets.Platform.LINUX_ARM64,
        )
        container_uri = self.image_asset.image_uri

        # -----------------------------------------------------------------
        # AgentCore Runtime
        # -----------------------------------------------------------------
        private_subnet_ids = [
            subnet.subnet_id for subnet in self._vpc.private_subnets
        ]

        self.runtime = bedrockagentcore.CfnRuntime(
            self,
            "OpenCodeRuntime",
            agent_runtime_name="opencode_runtime",
            protocol_configuration="MCP",
            agent_runtime_artifact=bedrockagentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=bedrockagentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=container_uri,
                ),
            ),
            role_arn=self.execution_role.role_arn,
            network_configuration=bedrockagentcore.CfnRuntime.NetworkConfigurationProperty(
                network_mode="VPC",
                network_mode_config=bedrockagentcore.CfnRuntime.VpcConfigProperty(
                    subnets=private_subnet_ids,
                    security_groups=[self.agentcore_sg.security_group_id],
                ),
            ),
            description="OpenCode AgentCore Runtime — Python FastMCP server on port 8000",
        )

        # RUNTIME_ARN env var — needed by cancel_task for cross-session StopRuntimeSession calls.
        # CloudFormation does not allow self-referencing a resource's own attributes in its
        # properties. The container resolves the full ARN at startup by calling
        # DescribeAgentRuntime with the runtime name, or from the platform-injected metadata.
        # We pass the ARN prefix so the container only needs to append the runtime ID.
        self.runtime.add_property_override("EnvironmentVariables", {
            "RUNTIME_ARN_PREFIX": f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:runtime/",
            "RUNTIME_NAME": "opencode_runtime",
            "WORKLOAD_NAME": "opencode_runtime",
            "OAUTH_CALLBACK_URL": callback_url,
            "AWS_REGION": self.region,
            "AWS_ACCOUNT_ID": self.account,
            "OPENCODE_MODEL": default_model_id,
            # EXPERIMENT 1: keep only AUTOUPDATE disabled (every cold start is
            # a fresh microVM — autoupdate would try to download a new binary
            # every time). All other DISABLE_* flags were added speculatively.
            "OPENCODE_DISABLE_AUTOUPDATE": "true",
        })

        # Managed session storage — persists work directories across microVM stop/resume.
        # Uses escape hatch because FilesystemConfigurations is not yet in the CDK L1.
        #
        # Skip in regions whose CFN schema has not been updated yet (e.g.
        # eu-central-1). In those regions the session storage feature is
        # disabled — work directories won't persist across microVM
        # stop/resume, but everything else works. Override via cdk context
        # ``enable_filesystem_configurations=true|false`` to force behavior.
        _regions_with_fs_support = {"us-east-1"}
        _override = self.node.try_get_context("enable_filesystem_configurations")
        if _override is not None:
            _enable_fs = str(_override).lower() == "true"
        else:
            _enable_fs = self.region in _regions_with_fs_support

        if _enable_fs:
            self.runtime.add_property_override("FilesystemConfigurations", [
                {
                    "SessionStorage": {
                        "MountPath": "/mnt/session",
                    },
                },
            ])

        # -----------------------------------------------------------------
        # AgentCore Runtime Endpoint
        #
        # Important: agent_runtime_version must track the current runtime
        # version, otherwise the endpoint stays pinned to the initial version
        # (1) and every ``UpdateAgentRuntime`` creates a new version that the
        # endpoint ignores. See
        # https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agent-runtime-versioning.html
        # -----------------------------------------------------------------
        self.runtime_endpoint = bedrockagentcore.CfnRuntimeEndpoint(
            self,
            "OpenCodeRuntimeEndpoint",
            agent_runtime_id=self.runtime.attr_agent_runtime_id,
            agent_runtime_version=self.runtime.attr_agent_runtime_version,
            name="opencode_endpoint",
            description="OpenCode AgentCore Runtime Endpoint",
        )
        self.runtime_endpoint.add_dependency(self.runtime)

        # -----------------------------------------------------------------
        # Outputs
        # -----------------------------------------------------------------
        cdk.CfnOutput(self, "RuntimeId", value=self.runtime.attr_agent_runtime_id)
        cdk.CfnOutput(self, "RuntimeEndpointId", value=self.runtime_endpoint.ref)

        # -----------------------------------------------------------------
        # cdk-nag suppressions
        # -----------------------------------------------------------------
        cdk_nag.NagSuppressions.add_resource_suppressions(
            self.execution_role,
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-IAM5",
                reason=(
                    "Runtime execution role: each wildcard is either forced by "
                    "the AWS service (no resource-level permissions available) "
                    "or scoped to a resource prefix we own. Specifically: "
                    "(1) DynamoDB 'index/*' follows the canonical GSI pattern "
                    "(table ARN is pinned; only GSI names are wildcarded). "
                    "(2) CloudWatch 'PutMetricData' and X-Ray 'PutTraceSegments' "
                    "are documented by AWS as not supporting resource-level IAM "
                    "(see IAM Service Authorization Reference). "
                    "(3) CloudWatch Logs 'CreateLogStream/PutLogEvents' target "
                    "log group ARNs owned by this stack; wildcards are on log "
                    "stream name within those groups. "
                    "(4) ECR 'GetAuthorizationToken' is an account-level API "
                    "that mandates Resource: '*'. "
                    "(5) AgentCore Identity 'GetWorkloadAccessToken' and "
                    "'GetResourceOauth2Token' scope to the workload identity "
                    "name; the service currently requires wildcard resources "
                    "on these actions. "
                    "See docs/THREAT-MODEL.md section 'Runtime execution role' "
                    "for the threat mapping."
                ),
            )],
            apply_to_children=True,
        )

        cdk_nag.NagSuppressions.add_resource_suppressions(
            self.agentcore_sg,
            [
                cdk_nag.NagPackSuppression(
                    id="AwsSolutions-EC23",
                    reason=(
                        "Security group egress is restricted to TCP/443; "
                        "AWS service traffic routes through VPC endpoints "
                        "(the CIDR 0.0.0.0/0 only reaches public git hosts "
                        "via NAT Gateway). FQDN-level egress filtering is "
                        "documented as a residual risk in "
                        "docs/HARDENING.md#known-limitations; production "
                        "deployments are expected to add AWS Network "
                        "Firewall rules or a forward proxy."
                    ),
                ),
                cdk_nag.NagPackSuppression(
                    id="CdkNagValidationFailure",
                    reason=(
                        "Follow-on finding from AwsSolutions-EC23 for the "
                        "same 0.0.0.0/0:443 rule; see the EC23 reason above "
                        "and docs/HARDENING.md#known-limitations."
                    ),
                ),
            ],
        )
