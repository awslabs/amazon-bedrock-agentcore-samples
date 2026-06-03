"""IAM role for the AgentCore Runtime container."""

from aws_cdk import Stack
from aws_cdk import aws_iam as iam
from constructs import Construct


class AgentCoreRole(iam.Role):
    """Execution role granted to the AgentCore Runtime container.

    Permissions granted:
      - ECR pull (for the container image)
      - CloudWatch Logs + X-Ray + per-namespace metrics
      - bedrock:InvokeModel for the Strands agent
      - bedrock-agentcore:GetWorkloadAccessToken* for OBO
      - bedrock-agentcore:GetResourceOauth2Token for AgentCore Identity
        (vends the Auth0 M2M and Atlassian 3LO tokens)
      - bedrock-agentcore:CreateEvent etc. on the memory resource
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        memory_arn: str,
        **kwargs,
    ):
        region = Stack.of(scope).region
        account = Stack.of(scope).account

        statements = [
            iam.PolicyStatement(
                sid="ECRImageAccess",
                actions=[
                    "ecr:BatchGetImage",
                    "ecr:GetDownloadUrlForLayer",
                    "ecr:BatchCheckLayerAvailability",
                ],
                resources=[f"arn:aws:ecr:{region}:{account}:repository/*"],
            ),
            iam.PolicyStatement(
                sid="ECRTokenAccess",
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"],
            ),
            iam.PolicyStatement(
                sid="Logs",
                actions=[
                    "logs:DescribeLogStreams",
                    "logs:CreateLogGroup",
                    "logs:DescribeLogGroups",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[
                    f"arn:aws:logs:{region}:{account}:log-group:/aws/bedrock-agentcore/runtimes/*"
                ],
            ),
            iam.PolicyStatement(
                sid="Telemetry",
                actions=[
                    "xray:PutTraceSegments",
                    "xray:PutTelemetryRecords",
                    "xray:GetSamplingRules",
                    "xray:GetSamplingTargets",
                ],
                resources=["*"],
            ),
            iam.PolicyStatement(
                sid="Metrics",
                actions=["cloudwatch:PutMetricData"],
                resources=["*"],
                conditions={"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}},
            ),
            iam.PolicyStatement(
                sid="GetAgentAccessToken",
                actions=[
                    "bedrock-agentcore:GetWorkloadAccessToken",
                    "bedrock-agentcore:GetWorkloadAccessTokenForJWT",
                    "bedrock-agentcore:GetWorkloadAccessTokenForUserId",
                ],
                resources=[
                    f"arn:aws:bedrock-agentcore:{region}:{account}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{region}:{account}:workload-identity-directory/default/workload-identity/*",
                ],
            ),
            iam.PolicyStatement(
                sid="GetOauth2TokenFromIdentity",
                actions=["bedrock-agentcore:GetResourceOauth2Token"],
                resources=["*"],
            ),
            iam.PolicyStatement(
                sid="BedrockModelInvocation",
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/*",
                    f"arn:aws:bedrock:{region}:{account}:*",
                ],
            ),
            iam.PolicyStatement(
                sid="MemoryEvents",
                actions=[
                    "bedrock-agentcore:CreateEvent",
                    "bedrock-agentcore:ListEvents",
                    "bedrock-agentcore:GetEvent",
                ],
                resources=[memory_arn],
            ),
        ]

        super().__init__(
            scope,
            construct_id,
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            inline_policies={
                "AgentCorePolicy": iam.PolicyDocument(statements=statements)
            },
            **kwargs,
        )
