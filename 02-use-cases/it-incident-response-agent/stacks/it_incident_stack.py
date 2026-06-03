"""Single-stack deployment for the IT Incident Response Agent.

Layers:
  1. Storage           : DynamoDB tables (Users, Processes, ChangeRequests),
                         seed bucket, KB document bucket. Jira is the system
                         of record for tickets; we don't shadow it locally.
  2. Knowledge Base    : OpenSearch Serverless collection + Bedrock KB +
                         S3 data source seeded with the runbooks under kb-docs/.
  3. Memory            : CfnMemory with EPISODIC strategy keyed per-user.
  4. AgentCore Identity: Auth0 + Atlassian client_secrets in Secrets
                         Manager, plus two OAuth2 credential providers
                         (custom resource) registered with AgentCore
                         Identity. The agent uses @requires_access_token
                         to vend tokens on demand; it never sees a secret.
  5. Tool Lambdas      : lookup_user, get_process_info, create_change_request,
                         query_kb (the KB wrapper, also a gateway tool).
  6. Gateway           : native CfnGateway with CUSTOM_JWT inbound auth
                         (Auth0) and one CfnGatewayTarget per Lambda tool.
  7. Runtime           : ECR repo + CodeBuild + agent CfnRuntime; runtime
                         env points GATEWAY_URL at the gateway's URL and
                         JIRA_MCP_URL at the Atlassian Remote MCP server.
  8. Trigger           : SNS topic + Lambda subscriber that invokes the
                         AgentCore Runtime with a Jira issue key.
  9. Evaluation        : online evaluation config (LLM-as-a-judge) reading
                         from the runtime's CloudWatch log group.
"""

import json
import os

from aws_cdk import (
    CfnOutput,
    CustomResource,
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import aws_bedrock as bedrock
from aws_cdk import aws_bedrockagentcore as bedrockagentcore
from aws_cdk import aws_codebuild as codebuild
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_lambda_event_sources as event_sources
from aws_cdk import aws_logs as logs
from aws_cdk import aws_opensearchserverless as oss
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_assets as s3_assets
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import aws_secretsmanager as secrets
from aws_cdk import aws_sns as sns
from constructs import Construct

from infra_utils import tool_schemas
from infra_utils.agentcore_role import AgentCoreRole

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ItIncidentStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, *, config: dict, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        self.config = config
        self._stack_slug = construct_id.lower().replace("-", "")

        self._build_storage()
        self._build_kb()
        self._build_identity_and_memory()
        self._build_secret()
        self._build_oauth_provider()
        self._build_tool_lambdas()
        self._build_gateway()
        self._build_runtime()
        self._build_trigger()
        self._build_evaluation()

        self._wire_outputs()

    # ------------------------------------------------------------------ #
    # Layer 1: storage                                                    #
    # ------------------------------------------------------------------ #
    def _build_storage(self) -> None:
        self.users_table = dynamodb.Table(
            self,
            "UsersTable",
            partition_key=dynamodb.Attribute(
                name="user_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.processes_table = dynamodb.Table(
            self,
            "ProcessesTable",
            partition_key=dynamodb.Attribute(
                name="process_name", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.changes_table = dynamodb.Table(
            self,
            "ChangeRequestsTable",
            partition_key=dynamodb.Attribute(
                name="change_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        self.seed_bucket = s3.Bucket(
            self,
            "SeedBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            versioned=False,
        )
        s3deploy.BucketDeployment(
            self,
            "SeedBucketDeploy",
            sources=[s3deploy.Source.asset(os.path.join(PROJECT_ROOT, "seed-data"))],
            destination_bucket=self.seed_bucket,
            destination_key_prefix="seed",
        )

        self.kb_bucket = s3.Bucket(
            self,
            "KbBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            versioned=False,
        )
        s3deploy.BucketDeployment(
            self,
            "KbDocsDeploy",
            sources=[s3deploy.Source.asset(os.path.join(PROJECT_ROOT, "kb-docs"))],
            destination_bucket=self.kb_bucket,
            destination_key_prefix="runbooks",
        )

    # ------------------------------------------------------------------ #
    # Layer 2: Knowledge Base on OpenSearch Serverless                    #
    # ------------------------------------------------------------------ #
    def _build_kb(self) -> None:
        # OSS collection + minimal-viable security policies
        collection_name = f"{self._stack_slug[:24]}-kb"
        self.oss_collection = oss.CfnCollection(
            self,
            "KbCollection",
            name=collection_name,
            type="VECTORSEARCH",
        )

        encryption_policy = oss.CfnSecurityPolicy(
            self,
            "KbEncryptionPolicy",
            name=f"{collection_name}-enc",
            type="encryption",
            policy=json.dumps(
                {
                    "Rules": [
                        {
                            "ResourceType": "collection",
                            "Resource": [f"collection/{collection_name}"],
                        }
                    ],
                    "AWSOwnedKey": True,
                }
            ),
        )
        network_policy = oss.CfnSecurityPolicy(
            self,
            "KbNetworkPolicy",
            name=f"{collection_name}-net",
            type="network",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/{collection_name}"],
                            },
                            {
                                "ResourceType": "dashboard",
                                "Resource": [f"collection/{collection_name}"],
                            },
                        ],
                        "AllowFromPublic": True,
                    }
                ]
            ),
        )
        self.oss_collection.add_dependency(encryption_policy)
        self.oss_collection.add_dependency(network_policy)

        # KB execution role
        self.kb_role = iam.Role(
            self,
            "KbRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            inline_policies={
                "KbPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["bedrock:InvokeModel"],
                            resources=[
                                f"arn:aws:bedrock:{self.region}::foundation-model/{self.config['kb_embedding_model_id']}"
                            ],
                        ),
                        iam.PolicyStatement(
                            actions=["aoss:APIAccessAll"],
                            resources=[self.oss_collection.attr_arn],
                        ),
                        iam.PolicyStatement(
                            actions=["s3:GetObject", "s3:ListBucket"],
                            resources=[
                                self.kb_bucket.bucket_arn,
                                f"{self.kb_bucket.bucket_arn}/*",
                            ],
                        ),
                    ]
                )
            },
        )

        # Data access policy for OSS — KB role + the deploying principal
        data_policy = oss.CfnAccessPolicy(
            self,
            "KbDataPolicy",
            name=f"{collection_name}-data",
            type="data",
            policy=json.dumps(
                [
                    {
                        "Rules": [
                            {
                                "ResourceType": "index",
                                "Resource": [f"index/{collection_name}/*"],
                                "Permission": [
                                    "aoss:CreateIndex",
                                    "aoss:DeleteIndex",
                                    "aoss:UpdateIndex",
                                    "aoss:DescribeIndex",
                                    "aoss:ReadDocument",
                                    "aoss:WriteDocument",
                                ],
                            },
                            {
                                "ResourceType": "collection",
                                "Resource": [f"collection/{collection_name}"],
                                "Permission": [
                                    "aoss:CreateCollectionItems",
                                    "aoss:DescribeCollectionItems",
                                    "aoss:UpdateCollectionItems",
                                ],
                            },
                        ],
                        "Principal": [
                            self.kb_role.role_arn,
                            f"arn:aws:iam::{self.account}:root",
                        ],
                    }
                ]
            ),
        )

        index_name = "it-runbooks"
        self.knowledge_base = bedrock.CfnKnowledgeBase(
            self,
            "KnowledgeBase",
            name=f"{construct_safe_name(self._stack_slug)}-kb",
            role_arn=self.kb_role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=f"arn:aws:bedrock:{self.region}::foundation-model/{self.config['kb_embedding_model_id']}"
                ),
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="OPENSEARCH_SERVERLESS",
                opensearch_serverless_configuration=bedrock.CfnKnowledgeBase.OpenSearchServerlessConfigurationProperty(
                    collection_arn=self.oss_collection.attr_arn,
                    vector_index_name=index_name,
                    field_mapping=bedrock.CfnKnowledgeBase.OpenSearchServerlessFieldMappingProperty(
                        vector_field="bedrock-knowledge-base-default-vector",
                        text_field="AMAZON_BEDROCK_TEXT_CHUNK",
                        metadata_field="AMAZON_BEDROCK_METADATA",
                    ),
                ),
            ),
        )
        self.knowledge_base.add_dependency(data_policy)
        self.knowledge_base.add_dependency(self.oss_collection)

        self.kb_data_source = bedrock.CfnDataSource(
            self,
            "KbDataSource",
            name="runbooks",
            knowledge_base_id=self.knowledge_base.attr_knowledge_base_id,
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                type="S3",
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=self.kb_bucket.bucket_arn,
                    inclusion_prefixes=["runbooks/"],
                ),
            ),
        )

    # ------------------------------------------------------------------ #
    # Layer 3 + 4: Identity + Memory                                      #
    # ------------------------------------------------------------------ #
    # AgentCore manages a workload identity for each runtime automatically;
    # we don't need to provision one explicitly.
    def _build_identity_and_memory(self) -> None:
        self.memory = bedrockagentcore.CfnMemory(
            self,
            "Memory",
            name=f"{construct_safe_name(self._stack_slug)}_memory",
            description="Episodic memory for IT incident response agent",
            event_expiry_duration=90,
            memory_strategies=[
                bedrockagentcore.CfnMemory.MemoryStrategyProperty(
                    summary_memory_strategy=bedrockagentcore.CfnMemory.SummaryMemoryStrategyProperty(
                        name="incident_episodes",
                        namespaces=["incidents/{actorId}"],
                    )
                )
            ],
        )

    # ------------------------------------------------------------------ #
    # IdP secrets (consumed only by the OAuth-provider custom resource;   #
    # the runtime never reads them directly)                              #
    # ------------------------------------------------------------------ #
    def _build_secret(self) -> None:
        self.auth0_secret = secrets.Secret(
            self,
            "Auth0Secret",
            description="Auth0 M2M client_secret (loaded into AgentCore Identity)",
            secret_string_value=secret_string(
                json.dumps({"client_secret": self.config["auth0_client_secret"]})
            ),
        )
        self.jira_secret = secrets.Secret(
            self,
            "JiraOauthSecret",
            description="Atlassian 3LO client_secret (loaded into AgentCore Identity)",
            secret_string_value=secret_string(
                json.dumps({"client_secret": self.config["jira_oauth_client_secret"]})
            ),
        )

    # ------------------------------------------------------------------ #
    # AgentCore OAuth2 credential providers (Auth0 M2M + Atlassian 3LO)   #
    # ------------------------------------------------------------------ #
    def _build_oauth_provider(self) -> None:
        """Provision two AgentCore Identity OAuth2 credential providers.

        - Auth0 (CustomOauth2): the agent calls the AgentCore Gateway
          using a Bearer JWT vended by Auth0 via client_credentials.
          `@requires_access_token(auth_flow="M2M")`.
        - Atlassian (AtlassianOauth2): the agent calls the Atlassian
          Remote MCP server using an OAuth 3LO access token.
          `@requires_access_token(auth_flow="USER_FEDERATION")`.

        Both vendors share one provisioner Lambda — it reads the
        relevant secret from Secrets Manager and shapes the provider
        config based on the `Vendor` property.
        """
        provider_fn = lambda_.Function(
            self,
            "OauthProviderFn",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="infra_utils.oauth_provider_lambda.handler",
            timeout=Duration.minutes(5),
            code=lambda_.Code.from_asset(
                PROJECT_ROOT,
                exclude=[
                    "*.pyc",
                    "__pycache__",
                    "cdk.out",
                    "agent-code",
                    "kb-docs",
                    "seed-data",
                    ".venv",
                    "node_modules",
                ],
            ),
        )
        self.auth0_secret.grant_read(provider_fn)
        self.jira_secret.grant_read(provider_fn)
        provider_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:CreateOauth2CredentialProvider",
                    "bedrock-agentcore:UpdateOauth2CredentialProvider",
                    "bedrock-agentcore:DeleteOauth2CredentialProvider",
                    "bedrock-agentcore:GetOauth2CredentialProvider",
                ],
                resources=["*"],
            )
        )

        # Auth0 M2M provider (gateway outbound)
        self.oauth_provider_name = f"{construct_safe_name(self._stack_slug)}_auth0_m2m"
        discovery_url = (
            f"https://{self.config['auth0_domain']}/.well-known/openid-configuration"
        )
        self.oauth_provider_cr = CustomResource(
            self,
            "OauthProviderCR",
            service_token=provider_fn.function_arn,
            properties={
                "ProviderName": self.oauth_provider_name,
                "Vendor": "CustomOauth2",
                "ClientId": self.config["auth0_client_id"],
                "SecretArn": self.auth0_secret.secret_arn,
                "DiscoveryUrl": discovery_url,
                "Version": "2",
            },
        )

        # Atlassian 3LO provider (Jira Remote MCP)
        self.jira_provider_name = (
            f"{construct_safe_name(self._stack_slug)}_jira_3lo"
        )
        self.jira_provider_cr = CustomResource(
            self,
            "JiraOauthProviderCR",
            service_token=provider_fn.function_arn,
            properties={
                "ProviderName": self.jira_provider_name,
                "Vendor": "AtlassianOauth2",
                "ClientId": self.config["jira_oauth_client_id"],
                "SecretArn": self.jira_secret.secret_arn,
                "Version": "1",
            },
        )

    # ------------------------------------------------------------------ #
    # Layer 5: Lambda tools                                               #
    # ------------------------------------------------------------------ #
    def _build_tool_lambdas(self) -> None:
        tools_asset_path = os.path.join(PROJECT_ROOT, "lambdas")

        common_env = {
            "USERS_TABLE": self.users_table.table_name,
            "PROCESSES_TABLE": self.processes_table.table_name,
            "CHANGES_TABLE": self.changes_table.table_name,
        }

        self.lookup_user_fn = lambda_.Function(
            self,
            "LookupUserFn",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="tools.lookup_user.lambda_handler",
            timeout=Duration.seconds(15),
            memory_size=256,
            code=lambda_.Code.from_asset(tools_asset_path),
            environment=common_env,
        )
        self.users_table.grant_read_data(self.lookup_user_fn)

        self.get_process_info_fn = lambda_.Function(
            self,
            "GetProcessInfoFn",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="tools.get_process_info.lambda_handler",
            timeout=Duration.seconds(15),
            memory_size=256,
            code=lambda_.Code.from_asset(tools_asset_path),
            environment=common_env,
        )
        self.processes_table.grant_read_data(self.get_process_info_fn)

        self.create_change_request_fn = lambda_.Function(
            self,
            "CreateChangeRequestFn",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="tools.create_change_request.lambda_handler",
            timeout=Duration.seconds(15),
            memory_size=256,
            code=lambda_.Code.from_asset(tools_asset_path),
            environment=common_env,
        )
        self.changes_table.grant_write_data(self.create_change_request_fn)
        self.users_table.grant_read_write_data(self.create_change_request_fn)

        self.query_kb_fn = lambda_.Function(
            self,
            "QueryKbFn",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="tools.query_kb.lambda_handler",
            timeout=Duration.seconds(30),
            memory_size=256,
            code=lambda_.Code.from_asset(tools_asset_path),
            environment={"KB_ID": self.knowledge_base.attr_knowledge_base_id},
        )
        self.query_kb_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:Retrieve"],
                resources=[self.knowledge_base.attr_knowledge_base_arn],
            )
        )

    # ------------------------------------------------------------------ #
    # Layer 6: Runtime container (CodeBuild + ECR + CfnRuntime)           #
    # ------------------------------------------------------------------ #
    def _build_runtime(self) -> None:
        self.ecr_repo = ecr.Repository(
            self,
            "AgentRepo",
            repository_name=f"{self._stack_slug}-it-agent",
            image_tag_mutability=ecr.TagMutability.MUTABLE,
            removal_policy=RemovalPolicy.DESTROY,
            empty_on_delete=True,
            image_scan_on_push=True,
        )

        agent_asset = s3_assets.Asset(
            self, "AgentSourceAsset", path=os.path.join(PROJECT_ROOT, "agent-code")
        )

        codebuild_role = iam.Role(
            self,
            "AgentBuildRole",
            assumed_by=iam.ServicePrincipal("codebuild.amazonaws.com"),
            inline_policies={
                "BuildPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                            ],
                            resources=[
                                f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/codebuild/*"
                            ],
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "ecr:BatchCheckLayerAvailability",
                                "ecr:GetDownloadUrlForLayer",
                                "ecr:BatchGetImage",
                                "ecr:GetAuthorizationToken",
                                "ecr:PutImage",
                                "ecr:InitiateLayerUpload",
                                "ecr:UploadLayerPart",
                                "ecr:CompleteLayerUpload",
                            ],
                            resources=[self.ecr_repo.repository_arn, "*"],
                        ),
                        iam.PolicyStatement(
                            actions=["s3:GetObject"],
                            resources=[f"{agent_asset.bucket.bucket_arn}/*"],
                        ),
                    ]
                )
            },
        )

        build_project = codebuild.Project(
            self,
            "AgentBuildProject",
            role=codebuild_role,
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxArmBuildImage.AMAZON_LINUX_2_STANDARD_3_0,
                compute_type=codebuild.ComputeType.LARGE,
                privileged=True,
            ),
            source=codebuild.Source.s3(
                bucket=agent_asset.bucket, path=agent_asset.s3_object_key
            ),
            build_spec=codebuild.BuildSpec.from_object(
                {
                    "version": "0.2",
                    "phases": {
                        "pre_build": {
                            "commands": [
                                "aws ecr get-login-password --region $AWS_DEFAULT_REGION "
                                "| docker login --username AWS --password-stdin "
                                "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com"
                            ]
                        },
                        "build": {
                            "commands": [
                                "docker build -t $REPO_NAME:$IMAGE_TAG .",
                                "docker tag $REPO_NAME:$IMAGE_TAG "
                                "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/$REPO_NAME:$IMAGE_TAG",
                            ]
                        },
                        "post_build": {
                            "commands": [
                                "docker push "
                                "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_DEFAULT_REGION.amazonaws.com/$REPO_NAME:$IMAGE_TAG"
                            ]
                        },
                    },
                }
            ),
            environment_variables={
                "AWS_DEFAULT_REGION": codebuild.BuildEnvironmentVariable(value=self.region),
                "AWS_ACCOUNT_ID": codebuild.BuildEnvironmentVariable(value=self.account),
                "REPO_NAME": codebuild.BuildEnvironmentVariable(value=self.ecr_repo.repository_name),
                "IMAGE_TAG": codebuild.BuildEnvironmentVariable(value="latest"),
            },
        )

        build_trigger_fn = lambda_.Function(
            self,
            "AgentBuildTriggerFn",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="infra_utils.build_trigger_lambda.handler",
            timeout=Duration.minutes(15),
            code=lambda_.Code.from_asset(
                PROJECT_ROOT,
                exclude=[
                    "*.pyc",
                    "__pycache__",
                    "cdk.out",
                    "agent-code",
                    "kb-docs",
                    "seed-data",
                    ".venv",
                    "node_modules",
                ],
            ),
            initial_policy=[
                iam.PolicyStatement(
                    actions=["codebuild:StartBuild", "codebuild:BatchGetBuilds"],
                    resources=[build_project.project_arn],
                )
            ],
        )

        trigger_build = CustomResource(
            self,
            "TriggerAgentBuild",
            service_token=build_trigger_fn.function_arn,
            properties={"ProjectName": build_project.project_name},
        )

        memory_arn = (
            f"arn:aws:bedrock-agentcore:{self.region}:{self.account}:memory/"
            f"{self.memory.attr_memory_id}"
        )
        self.agent_role = AgentCoreRole(
            self,
            "AgentCoreRole",
            memory_arn=memory_arn,
        )

        # CloudWatch log group for ADOT/OTEL telemetry from the runtime.
        # The OTEL HTTP exporter targets this log group via the
        # OTEL_EXPORTER_OTLP_LOGS_HEADERS env var on the runtime container.
        self.runtime_log_group_name = (
            f"/aws/bedrock-agentcore/runtimes/{self._stack_slug}"
        )
        self.runtime_log_group = logs.LogGroup(
            self,
            "RuntimeLogGroup",
            log_group_name=self.runtime_log_group_name,
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.otel_service_name = f"{construct_safe_name(self._stack_slug)}_agent"

        self.agent_runtime = bedrockagentcore.CfnRuntime(
            self,
            "AgentRuntime",
            agent_runtime_name=f"{construct_safe_name(self._stack_slug)}_agent",
            agent_runtime_artifact=bedrockagentcore.CfnRuntime.AgentRuntimeArtifactProperty(
                container_configuration=bedrockagentcore.CfnRuntime.ContainerConfigurationProperty(
                    container_uri=f"{self.ecr_repo.repository_uri}:latest"
                )
            ),
            network_configuration=bedrockagentcore.CfnRuntime.NetworkConfigurationProperty(
                network_mode="PUBLIC"
            ),
            protocol_configuration="HTTP",
            role_arn=self.agent_role.role_arn,
            description="IT incident response agent runtime",
            environment_variables={
                "AWS_DEFAULT_REGION": self.region,
                "MEMORY_ID": self.memory.attr_memory_id,
                "AGENT_MODEL_ID": self.config["agent_model_id"],
                "GATEWAY_URL": self.gateway.attr_gateway_url,
                "OAUTH_PROVIDER_NAME": self.oauth_provider_name,
                "GATEWAY_AUDIENCE": self.config["auth0_audience"],
                # Jira Remote MCP (Atlassian 3LO).
                "JIRA_OAUTH_PROVIDER_NAME": self.jira_provider_name,
                "JIRA_MCP_URL": "https://mcp.atlassian.com/v1/sse",
                "JIRA_SITE_URL": self.config["jira_site_url"],
                "JIRA_PROJECT_KEY": self.config["jira_project_key"],
                # AgentCore Observability via AWS Distro for OpenTelemetry.
                # The Dockerfile already wraps the entrypoint with
                # `opentelemetry-instrument`. These env vars route spans +
                # logs to CloudWatch GenAI Observability.
                "AGENT_OBSERVABILITY_ENABLED": "true",
                "OTEL_PYTHON_DISTRO": "aws_distro",
                "OTEL_PYTHON_CONFIGURATOR": "aws_configurator",
                "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
                "OTEL_TRACES_EXPORTER": "otlp",
                "OTEL_EXPORTER_OTLP_LOGS_HEADERS": (
                    f"x-aws-log-group={self.runtime_log_group_name},"
                    "x-aws-log-stream=default,"
                    "x-aws-metric-namespace=bedrock-agentcore"
                ),
                "OTEL_RESOURCE_ATTRIBUTES": f"service.name={self.otel_service_name}",
            },
        )
        self.agent_runtime.node.add_dependency(trigger_build)
        self.agent_runtime.node.add_dependency(self.memory)
        self.agent_runtime.node.add_dependency(self.gateway)
        self.agent_runtime.node.add_dependency(self.oauth_provider_cr)
        self.agent_runtime.node.add_dependency(self.jira_provider_cr)

        # The seeder runs after KB exists and DDB tables exist.
        seeder_fn = lambda_.Function(
            self,
            "SeederFn",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="infra_utils.seeder_lambda.handler",
            timeout=Duration.minutes(10),
            code=lambda_.Code.from_asset(
                PROJECT_ROOT,
                exclude=[
                    "*.pyc",
                    "__pycache__",
                    "cdk.out",
                    "agent-code",
                    "kb-docs",
                    "seed-data",
                    ".venv",
                    "node_modules",
                ],
            ),
        )
        self.seed_bucket.grant_read(seeder_fn)
        self.users_table.grant_write_data(seeder_fn)
        self.processes_table.grant_write_data(seeder_fn)
        seeder_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:StartIngestionJob",
                    "bedrock:GetIngestionJob",
                ],
                resources=[self.knowledge_base.attr_knowledge_base_arn],
            )
        )

        seed_cr = CustomResource(
            self,
            "TriggerSeeder",
            service_token=seeder_fn.function_arn,
            properties={
                "SeedBucket": self.seed_bucket.bucket_name,
                "UsersTable": self.users_table.table_name,
                "ProcessesTable": self.processes_table.table_name,
                "KnowledgeBaseId": self.knowledge_base.attr_knowledge_base_id,
                "DataSourceId": self.kb_data_source.attr_data_source_id,
            },
        )
        seed_cr.node.add_dependency(self.kb_data_source)

    # ------------------------------------------------------------------ #
    # Layer 6: Gateway (native CDK L1 — CUSTOM_JWT inbound, Lambda targets) #
    # ------------------------------------------------------------------ #
    def _build_gateway(self) -> None:
        gateway_role = iam.Role(
            self,
            "GatewayRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            inline_policies={
                "GatewayPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["lambda:InvokeFunction"],
                            resources=[
                                self.lookup_user_fn.function_arn,
                                self.get_process_info_fn.function_arn,
                                self.create_change_request_fn.function_arn,
                                self.query_kb_fn.function_arn,
                            ],
                        ),
                        iam.PolicyStatement(
                            actions=[
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents",
                            ],
                            resources=["*"],
                        ),
                    ]
                )
            },
        )

        discovery_url = (
            f"https://{self.config['auth0_domain']}/.well-known/openid-configuration"
        )

        self.gateway = bedrockagentcore.CfnGateway(
            self,
            "Gateway",
            name=f"{construct_safe_name(self._stack_slug)}_gw",
            role_arn=gateway_role.role_arn,
            protocol_type="MCP",
            authorizer_type="CUSTOM_JWT",
            authorizer_configuration=bedrockagentcore.CfnGateway.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=bedrockagentcore.CfnGateway.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=discovery_url,
                    allowed_audience=[self.config["auth0_audience"]],
                )
            ),
            description="IT incident response gateway",
        )

        self._build_gateway_target(
            "LookupUserTarget",
            tool_schemas.LOOKUP_USER,
            self.lookup_user_fn,
        )
        self._build_gateway_target(
            "GetProcessInfoTarget",
            tool_schemas.GET_PROCESS_INFO,
            self.get_process_info_fn,
        )
        self._build_gateway_target(
            "CreateChangeRequestTarget",
            tool_schemas.CREATE_CHANGE_REQUEST,
            self.create_change_request_fn,
        )
        self._build_gateway_target(
            "QueryKbTarget",
            tool_schemas.QUERY_KB,
            self.query_kb_fn,
        )

    def _build_gateway_target(self, construct_id: str, schema: dict, fn: lambda_.Function) -> None:
        target = bedrockagentcore.CfnGatewayTarget(
            self,
            construct_id,
            gateway_identifier=self.gateway.attr_gateway_identifier,
            name=schema["name"],
            description=schema.get("description", ""),
            target_configuration=bedrockagentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=bedrockagentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    lambda_=bedrockagentcore.CfnGatewayTarget.McpLambdaTargetConfigurationProperty(
                        lambda_arn=fn.function_arn,
                        tool_schema=bedrockagentcore.CfnGatewayTarget.ToolSchemaProperty(
                            inline_payload=[
                                bedrockagentcore.CfnGatewayTarget.ToolDefinitionProperty(
                                    name=schema["name"],
                                    description=schema["description"],
                                    input_schema=_to_schema_definition(schema["inputSchema"]),
                                )
                            ]
                        ),
                    )
                )
            ),
            credential_provider_configurations=[
                bedrockagentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE",
                )
            ],
        )
        target.node.add_dependency(self.gateway)

    # ------------------------------------------------------------------ #
    # Layer 8: Trigger (SNS -> Lambda -> AgentCore)                        #
    # ------------------------------------------------------------------ #
    def _build_trigger(self) -> None:
        self.tickets_topic = sns.Topic(
            self,
            "TicketsTopic",
            display_name="JiraIssueCreated",
        )

        trigger_fn = lambda_.Function(
            self,
            "TicketEventHandlerFn",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="trigger.ticket_event_handler.lambda_handler",
            timeout=Duration.minutes(5),
            memory_size=256,
            code=lambda_.Code.from_asset(os.path.join(PROJECT_ROOT, "lambdas")),
            environment={
                "AGENT_RUNTIME_ARN": self.agent_runtime.attr_agent_runtime_arn,
            },
        )
        trigger_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock-agentcore:InvokeAgentRuntime"],
                resources=[self.agent_runtime.attr_agent_runtime_arn + "/*", self.agent_runtime.attr_agent_runtime_arn],
            )
        )
        trigger_fn.add_event_source(event_sources.SnsEventSource(self.tickets_topic))

        self.trigger_fn = trigger_fn

    # ------------------------------------------------------------------ #
    # Layer 9: AgentCore Online Evaluation                                #
    # ------------------------------------------------------------------ #
    def _build_evaluation(self) -> None:
        """Stand up an online evaluation config over the runtime log group.

        AgentCore samples runtime spans/sessions from CloudWatch, runs the
        listed built-in LLM-as-a-judge evaluators on each sample, and
        emits results back to CloudWatch. No L1 construct exists yet; we
        wire it through `infra_utils/online_eval_provider_lambda.py`.

        The on-demand evaluation flow (one-off run against a specific
        session) is in `scripts/evaluate.py` and uses the same evaluator
        IDs plus a custom evaluator created at script-time.
        """
        eval_exec_role = iam.Role(
            self,
            "EvaluationExecutionRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            inline_policies={
                "EvalPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            sid="ReadRuntimeLogs",
                            actions=[
                                "logs:FilterLogEvents",
                                "logs:GetLogEvents",
                                "logs:DescribeLogGroups",
                                "logs:DescribeLogStreams",
                                "logs:StartQuery",
                                "logs:StopQuery",
                                "logs:GetQueryResults",
                            ],
                            resources=[
                                self.runtime_log_group.log_group_arn,
                                f"{self.runtime_log_group.log_group_arn}:*",
                            ],
                        ),
                        iam.PolicyStatement(
                            sid="InvokeJudgeModel",
                            actions=["bedrock:InvokeModel"],
                            resources=[
                                f"arn:aws:bedrock:{self.region}::foundation-model/*",
                                f"arn:aws:bedrock:{self.region}:{self.account}:inference-profile/*",
                            ],
                        ),
                    ]
                )
            },
        )

        eval_provider_fn = lambda_.Function(
            self,
            "OnlineEvalProviderFn",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="infra_utils.online_eval_provider_lambda.handler",
            timeout=Duration.minutes(5),
            code=lambda_.Code.from_asset(
                PROJECT_ROOT,
                exclude=[
                    "*.pyc",
                    "__pycache__",
                    "cdk.out",
                    "agent-code",
                    "kb-docs",
                    "seed-data",
                    ".venv",
                    "node_modules",
                ],
            ),
        )
        eval_provider_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock-agentcore:CreateOnlineEvaluationConfig",
                    "bedrock-agentcore:UpdateOnlineEvaluationConfig",
                    "bedrock-agentcore:DeleteOnlineEvaluationConfig",
                    "bedrock-agentcore:GetOnlineEvaluationConfig",
                    "bedrock-agentcore:ListOnlineEvaluationConfigs",
                ],
                resources=["*"],
            )
        )
        eval_provider_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[eval_exec_role.role_arn],
            )
        )

        self.online_eval_config_name = (
            f"{construct_safe_name(self._stack_slug)}_online_eval"
        )
        self.online_eval_cr = CustomResource(
            self,
            "OnlineEvalCR",
            service_token=eval_provider_fn.function_arn,
            properties={
                "ConfigName": self.online_eval_config_name,
                "Description": "Online eval for IT incident response agent",
                "LogGroupName": self.runtime_log_group_name,
                "ServiceName": f"{self.otel_service_name}.DEFAULT",
                "RoleArn": eval_exec_role.role_arn,
                "SamplingPercentage": "20",
                "BuiltinEvaluators": [
                    "GoalSuccessRate",
                    "Correctness",
                    "Helpfulness",
                    "ToolSelectionAccuracy",
                ],
                # Bump to force update when evaluator list changes
                "Version": "1",
            },
        )
        self.online_eval_cr.node.add_dependency(self.runtime_log_group)
        self.online_eval_cr.node.add_dependency(self.agent_runtime)

    # ------------------------------------------------------------------ #
    # Outputs                                                             #
    # ------------------------------------------------------------------ #
    def _wire_outputs(self) -> None:
        CfnOutput(self, "TicketsTopicArn", value=self.tickets_topic.topic_arn)
        CfnOutput(self, "AgentRuntimeArn", value=self.agent_runtime.attr_agent_runtime_arn)
        CfnOutput(self, "GatewayUrl", value=self.gateway.attr_gateway_url)
        CfnOutput(self, "GatewayId", value=self.gateway.attr_gateway_identifier)
        CfnOutput(self, "MemoryId", value=self.memory.attr_memory_id)
        CfnOutput(self, "KnowledgeBaseId", value=self.knowledge_base.attr_knowledge_base_id)
        CfnOutput(self, "RuntimeLogGroupName", value=self.runtime_log_group_name)
        CfnOutput(self, "OtelServiceName", value=self.otel_service_name)
        CfnOutput(self, "OnlineEvalConfigName", value=self.online_eval_config_name)
        CfnOutput(self, "JiraOauthProviderName", value=self.jira_provider_name)
        CfnOutput(
            self,
            "JiraOauthCallbackUrl",
            value=self.jira_provider_cr.get_att_string("CallbackUrl"),
            description="Add this URL to the Atlassian OAuth app's allowed callback URLs",
        )


def construct_safe_name(s: str) -> str:
    """AgentCore names allow [a-zA-Z0-9_]+; replace anything else."""
    return "".join(c if (c.isalnum() or c == "_") else "_" for c in s)


def secret_string(value: str):
    """Lazy import alias to avoid CDK import at module top."""
    from aws_cdk import SecretValue

    return SecretValue.unsafe_plain_text(value)


def _to_schema_definition(json_schema: dict):
    """Convert a JSON-Schema dict to CfnGatewayTarget.SchemaDefinitionProperty.

    Only handles the subset we actually use: object schemas with named
    properties whose types are string / integer / number / boolean.
    """
    return bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
        type=json_schema.get("type", "object"),
        description=json_schema.get("description"),
        properties={
            name: bedrockagentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                type=spec.get("type", "string"),
                description=spec.get("description"),
            )
            for name, spec in json_schema.get("properties", {}).items()
        },
        required=json_schema.get("required"),
    )
