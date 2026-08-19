"""Agent runtime construct for Bedrock agent IAM role"""

from constructs import Construct
from aws_cdk import aws_iam as iam, aws_sqs as sqs


class AgentRuntimeConstruct(Construct):
    """Construct for Bedrock Agent Runtime IAM role and permissions."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        region: str,
        usage_queue: sqs.Queue,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # IAM role for Bedrock Agent Runtime with least-privilege permissions
        self.agent_role = iam.Role(
            self,
            "BedrockAgentRole",
            role_name=f"AmazonBedrockAgentCoreSDKRuntime-{region}",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            inline_policies={
                "BedrockAgentCorePolicy": iam.PolicyDocument(
                    statements=[
                        # Bedrock model invocation permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream",
                            ],
                            resources=[f"arn:aws:bedrock:{region}::foundation-model/*"],
                        ),
                        # AgentCore runtime permissions
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock-agentcore:InvokeAgent",
                                "bedrock-agentcore:GetAgent",
                            ],
                            resources=["*"],  # AgentCore resources are tenant-isolated
                        ),
                    ]
                )
            },
        )

        # Grant agent role permission to send to SQS
        usage_queue.grant_send_messages(self.agent_role)
