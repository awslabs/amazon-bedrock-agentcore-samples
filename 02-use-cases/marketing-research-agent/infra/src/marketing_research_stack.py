from aws_cdk import (
    Stack,
    CfnOutput,
    RemovalPolicy,
    aws_ecs as ecs,
    aws_ecr as ecr,
    aws_ecs_patterns as ecs_patterns,
    aws_bedrockagentcore as agentcore,
    aws_iam as iam,
    aws_dynamodb as dynamodb,
)
from constructs import Construct
import re

class MarketingResearchStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, ecr_repository_arn: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Validate ecr_repository_arn
        if not ecr_repository_arn or not re.match(
              r'^arn:aws:ecr:[a-z0-9-]+:\d{12}:repository/[a-zA-Z0-9-_]+$',
              ecr_repository_arn):
            raise ValueError("Invalid ECR repository ARN provided")

        # Import existing ECR repository
        repository = ecr.Repository.from_repository_arn(
            self, "MarketingResearchRepo",
            repository_arn=ecr_repository_arn
        )
        
        # Get container URI for latest tag
        container_uri = repository.repository_uri_for_tag("latest")
        
        # Create IAM role for AgentCore runtime
        agentcore_role = iam.Role(
            self, "MarketingResearchRole",
            role_name="marketing_research_agentcore_role",
            assumed_by=iam.ServicePrincipal(
                "bedrock-agentcore.amazonaws.com",
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:*"}
                }
            ),
            inline_policies={
                "AgentCoreRuntimePolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            sid="ECRImageAccess",
                            effect=iam.Effect.ALLOW,
                            actions=["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
                            resources=[f"arn:aws:ecr:{self.region}:{self.account}:repository/*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["logs:DescribeLogStreams", "logs:CreateLogGroup"],
                            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock-agentcore/runtimes/*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["logs:DescribeLogGroups"],
                            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*"]
                        ),
                        iam.PolicyStatement(
                            sid="ECRTokenAccess",
                            effect=iam.Effect.ALLOW,
                            actions=["ecr:GetAuthorizationToken"],
                            resources=["*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["xray:PutTraceSegments", "xray:PutTelemetryRecords", "xray:GetSamplingRules", "xray:GetSamplingTargets"],
                            resources=["*"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["cloudwatch:PutMetricData"],
                            resources=["*"],
                            conditions={"StringEquals": {"cloudwatch:namespace": "bedrock-agentcore"}}
                        ),
                        iam.PolicyStatement(
                            sid="BedrockModelInvocation",
                            effect=iam.Effect.ALLOW,
                            actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream", "bedrock:ApplyGuardrail"],
                            resources=["arn:aws:bedrock:*::foundation-model/*", f"arn:aws:bedrock:{self.region}:{self.account}:*"]
                        ),
                        iam.PolicyStatement(
                            sid="AgentCoreMemoryAccess",
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "bedrock-agentcore:CreateMemory",
                                "bedrock-agentcore:GetMemory",
                                "bedrock-agentcore:UpdateMemory",
                                "bedrock-agentcore:DeleteMemory",
                                "bedrock-agentcore:ListMemories",
                                "bedrock-agentcore:CreateEvent",
                                "bedrock-agentcore:GetEvent",
                                "bedrock-agentcore:ListEvents",
                                "bedrock-agentcore:RetrieveMemoryRecords",
                                "bedrock-agentcore:GetMemoryRecord",
                                "bedrock-agentcore:ListMemoryRecords"
                            ],
                            resources=[f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:memory/*"]
                        ),
                        iam.PolicyStatement(
                            sid="EmbeddingModelAccess",
                            effect=iam.Effect.ALLOW,
                            actions=["bedrock:InvokeModel"],
                            resources=[
                                "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v1",
                                "arn:aws:bedrock:*::foundation-model/amazon.titan-embed-text-v2:0",
                                "arn:aws:bedrock:*::foundation-model/cohere.embed-english-v3",
                                "arn:aws:bedrock:*::foundation-model/cohere.embed-multilingual-v3"
                            ]
                        ),
                        iam.PolicyStatement(
                            sid="DynamoDBAccess",
                            effect=iam.Effect.ALLOW,
                            actions=[
                                "dynamodb:GetItem",
                                "dynamodb:PutItem",
                                "dynamodb:UpdateItem",
                                "dynamodb:DeleteItem",
                                "dynamodb:Query",
                                "dynamodb:Scan",
                                "dynamodb:BatchGetItem",
                                "dynamodb:BatchWriteItem"
                            ],
                            resources=[f"arn:aws:dynamodb:{self.region}:{self.account}:table/marketing-customer-data*"]
                        )
                    ]
                )
            }
        )

        # Create DynamoDB table for customer data
        customer_table = dynamodb.Table(
            self, "MarketingCustomerData",
            table_name="marketing-customer-data",
            partition_key=dynamodb.Attribute(
                name="customer_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Add Global Secondary Index for marketing channel queries
        customer_table.add_global_secondary_index(
            index_name="marketing-channel-index",
            partition_key=dynamodb.Attribute(
                name="marketing_channel",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING
            )
        )

        # Add Global Secondary Index for customer segment queries
        customer_table.add_global_secondary_index(
            index_name="customer-segment-index",
            partition_key=dynamodb.Attribute(
                name="customer_segment",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING
            )
        )

        cfn_runtime = agentcore.CfnRuntime(self, "MarketingResearchRuntime",
            agent_runtime_artifact=agentcore.CfnRuntime.AgentRuntimeArtifactProperty(
              container_configuration=agentcore.CfnRuntime.ContainerConfigurationProperty(
                  container_uri=container_uri
              )
            ),
            agent_runtime_name="marketing_research",
            network_configuration=agentcore.CfnRuntime.NetworkConfigurationProperty(
              network_mode="PUBLIC"
            ),
            role_arn=agentcore_role.role_arn
        )
        
        # Output the AgentCore runtime ARN
        CfnOutput(
            self, "AgentCoreRuntimeArn",
            value=cfn_runtime.attr_agent_runtime_arn,
            description="ARN of the AgentCore runtime"
        )

        # Output the DynamoDB table name
        CfnOutput(
            self, "CustomerTableName",
            value=customer_table.table_name,
            description="Name of the customer data DynamoDB table"
        )
