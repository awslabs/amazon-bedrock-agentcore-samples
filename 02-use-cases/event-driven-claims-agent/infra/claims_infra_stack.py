"""CDK stack for event-driven claims agent — Full CDK L2 with AgentCore constructs.

Deploys everything in a single `cdk deploy`:
- DynamoDB, S3, SNS, Cognito, EventBridge (infra)
- 7 Lambda functions (tools + trigger)
- AgentCore Runtime (dual-agent, Cognito auth)
- AgentCore Gateway (MCP, 6 Lambda targets, default Cognito M2M)
- AgentCore Memory (SEMANTIC + SUMMARIZATION)
- AgentCore Online Evaluation (built-in + custom LLM-as-judge)
- Observability (X-Ray tracing + CloudWatch logs)
"""

from aws_cdk import (
    CfnOutput,
    Duration,
    RemovalPolicy,
    Stack,
    Tags,
    aws_bedrockagentcore as agentcore,
    aws_bedrock_agentcore_alpha as agentcore_alpha,
    aws_cognito as cognito,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_s3 as s3,
    aws_sns as sns,
)
from constructs import Construct


class ClaimsInfraStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)
        Tags.of(self).add("auto-delete", "no")

        # ======================================================================
        # INFRASTRUCTURE (existing resources)
        # ======================================================================

        # --- DynamoDB Tables ---
        policies_table = dynamodb.Table(
            self,
            "PoliciesTable",
            table_name="ClaimsAgent-Policies",
            partition_key=dynamodb.Attribute(name="policy_number", type=dynamodb.AttributeType.STRING),
            removal_policy=RemovalPolicy.DESTROY,
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )
        claims_table = dynamodb.Table(
            self,
            "ClaimsTable",
            table_name="ClaimsAgent-Claims",
            partition_key=dynamodb.Attribute(name="claim_id", type=dynamodb.AttributeType.STRING),
            removal_policy=RemovalPolicy.DESTROY,
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )
        reviews_table = dynamodb.Table(
            self,
            "ReviewsTable",
            table_name="ClaimsAgent-Reviews",
            partition_key=dynamodb.Attribute(name="review_id", type=dynamodb.AttributeType.STRING),
            removal_policy=RemovalPolicy.DESTROY,
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        # --- SNS Topic for human review ---
        review_topic = sns.Topic(self, "ReviewTopic", topic_name="ClaimsAgent-HumanReview")

        # --- S3 Bucket for claim inbox ---
        inbox_bucket = s3.Bucket(
            self,
            "InboxBucket",
            bucket_name=f"claims-inbox-{self.account}-{self.region}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
            event_bridge_enabled=True,
        )

        # --- Cognito User Pool + App Client (M2M) for external callers ---
        user_pool = cognito.UserPool(
            self,
            "ClaimsUserPool",
            user_pool_name="ClaimsAgent-UserPool",
            removal_policy=RemovalPolicy.DESTROY,
        )
        resource_server = user_pool.add_resource_server(
            "AgentCoreRS",
            identifier="agentcore",
            scopes=[cognito.ResourceServerScope(scope_name="invoke", scope_description="Invoke agent")],
        )
        app_client = user_pool.add_client(
            "M2MClient",
            user_pool_client_name="ClaimsAgent-M2M",
            generate_secret=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(client_credentials=True),
                scopes=[
                    cognito.OAuthScope.resource_server(
                        resource_server,
                        cognito.ResourceServerScope(scope_name="invoke", scope_description="Invoke agent"),
                    )
                ],
            ),
        )
        domain = user_pool.add_domain(
            "CognitoDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"claims-agent-{self.account}",
            ),
        )

        CfnOutput(self, "UserPoolId", value=user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=app_client.user_pool_client_id)

        # ======================================================================
        # LAMBDA FUNCTIONS (tools for the agent via Gateway)
        # ======================================================================

        # --- Lambda: policy_lookup ---
        policy_lookup_fn = lambda_.Function(
            self,
            "PolicyLookupFn",
            function_name="ClaimsAgent-PolicyLookup",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset("../lambdas/policy_lookup"),
            environment={"POLICIES_TABLE": policies_table.table_name},
            timeout=Duration.seconds(10),
        )
        policies_table.grant_read_data(policy_lookup_fn)

        # --- Lambda: create_claim ---
        create_claim_fn = lambda_.Function(
            self,
            "CreateClaimFn",
            function_name="ClaimsAgent-CreateClaim",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset("../lambdas/create_claim"),
            environment={"CLAIMS_TABLE": claims_table.table_name},
            timeout=Duration.seconds(10),
        )
        claims_table.grant_read_write_data(create_claim_fn)

        # --- Lambda: human_review ---
        human_review_fn = lambda_.Function(
            self,
            "HumanReviewFn",
            function_name="ClaimsAgent-HumanReview",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset("../lambdas/human_review"),
            environment={
                "REVIEWS_TABLE": reviews_table.table_name,
                "REVIEW_SNS_TOPIC_ARN": review_topic.topic_arn,
            },
            timeout=Duration.seconds(10),
        )
        reviews_table.grant_read_write_data(human_review_fn)
        review_topic.grant_publish(human_review_fn)

        # --- Lambda: notification ---
        notification_fn = lambda_.Function(
            self,
            "NotificationFn",
            function_name="ClaimsAgent-Notification",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset("../lambdas/notification"),
            environment={"SENDER_EMAIL": self.node.try_get_context("sender_email") or "noreply@example.com"},
            timeout=Duration.seconds(10),
        )
        notification_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=["ses:SendEmail", "ses:SendRawEmail"],
                resources=["*"],
            )
        )

        # --- Lambda: list_pending_claims ---
        list_pending_fn = lambda_.Function(
            self,
            "ListPendingFn",
            function_name="ClaimsAgent-ListPending",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset("../lambdas/list_pending_claims"),
            environment={"CLAIMS_TABLE": claims_table.table_name},
            timeout=Duration.seconds(10),
        )
        claims_table.grant_read_data(list_pending_fn)

        # --- Lambda: resolve_claim ---
        resolve_claim_fn = lambda_.Function(
            self,
            "ResolveClaimFn",
            function_name="ClaimsAgent-ResolveClaim",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset("../lambdas/resolve_claim"),
            environment={
                "CLAIMS_TABLE": claims_table.table_name,
                "REVIEWS_TABLE": reviews_table.table_name,
            },
            timeout=Duration.seconds(10),
        )
        claims_table.grant_read_write_data(resolve_claim_fn)
        reviews_table.grant_read_write_data(resolve_claim_fn)

        # ======================================================================
        # AGENTCORE GATEWAY (MCP, 6 Lambda targets, default Cognito M2M auth)
        # ======================================================================

        # --- Policy Engine (created BEFORE gateway so it can be referenced) ---
        policy_engine = agentcore_alpha.PolicyEngine(
            self,
            "ClaimsPolicyEngine",
            policy_engine_name="claims_pe_cdk_v3",
            description="Cedar policy engine for claims processing authorization",
        )

        # Gateway with default Cognito M2M auth (auto-creates user pool for M2M)
        # This provides workload identity for the Runtime to call tools securely
        gateway = agentcore_alpha.Gateway(
            self,
            "ClaimsGateway",
            gateway_name="claims-gateway",
            description="MCP Gateway for claims processing tools",
            policy_engine_configuration=agentcore_alpha.GatewayPolicyEngineConfig(
                policy_engine=policy_engine,
                mode=agentcore_alpha.PolicyEngineMode.ENFORCE,
            ),
            protocol_configuration=agentcore.McpProtocolConfiguration(
                instructions="Gateway providing insurance claims processing tools: policy lookup, claim creation, human review, notifications, and claim resolution.",
                search_type=agentcore.McpGatewaySearchType.SEMANTIC,
            ),
        )

        # Add 6 Lambda targets with tool schemas
        gateway.add_lambda_target(
            "PolicyLookup",
            gateway_target_name="policy-lookup",
            description="Look up insurance policy details by policy number",
            lambda_function=policy_lookup_fn,
            tool_schema=agentcore_alpha.ToolSchema.from_local_asset("../lambdas/schemas/policy_lookup.json"),
        )

        gateway.add_lambda_target(
            "CreateClaim",
            gateway_target_name="create-claim",
            description="Create a new insurance claim",
            lambda_function=create_claim_fn,
            tool_schema=agentcore_alpha.ToolSchema.from_local_asset("../lambdas/schemas/create_claim.json"),
        )

        gateway.add_lambda_target(
            "HumanReview",
            gateway_target_name="human-review",
            description="Submit a claim for human review",
            lambda_function=human_review_fn,
            tool_schema=agentcore_alpha.ToolSchema.from_local_asset("../lambdas/schemas/human_review.json"),
        )

        gateway.add_lambda_target(
            "Notification",
            gateway_target_name="notification",
            description="Send email notification to claimant",
            lambda_function=notification_fn,
            tool_schema=agentcore_alpha.ToolSchema.from_local_asset("../lambdas/schemas/notification.json"),
        )

        gateway.add_lambda_target(
            "ListPendingClaims",
            gateway_target_name="list-pending-claims",
            description="List all claims pending review",
            lambda_function=list_pending_fn,
            tool_schema=agentcore_alpha.ToolSchema.from_local_asset("../lambdas/schemas/list_pending_claims.json"),
        )

        gateway.add_lambda_target(
            "ResolveClaim",
            gateway_target_name="resolve-claim",
            description="Resolve/approve/reject a pending claim",
            lambda_function=resolve_claim_fn,
            tool_schema=agentcore_alpha.ToolSchema.from_local_asset("../lambdas/schemas/resolve_claim.json"),
        )

        # Export gateway URL for reference
        CfnOutput(self, "GatewayUrl", value=gateway.gateway_url)

        # ======================================================================
        # AGENTCORE POLICY ENGINE (ALPHA — Cedar authorization policies)
        # ======================================================================

        # Cedar Policy: Allow all tool actions on this gateway (with IGNORE_ALL_FINDINGS)
        policy_engine.add_policy(
            "AllowAllTools",
            definition=f'permit(principal, action, resource == AgentCore::Gateway::"{gateway.gateway_arn}");',
            description="Permit all tool calls on the claims gateway",
            validation_mode=agentcore_alpha.PolicyValidationMode.IGNORE_ALL_FINDINGS,
        )

        # Cedar Policy: Block high-value claims (>= $100k) — uses type-safe builder
        policy_engine.add_policy(
            "BlockExcessiveClaims",
            definition=f'forbid(principal, action == AgentCore::Action::"create-claim___create_claim", resource == AgentCore::Gateway::"{gateway.gateway_arn}") when {{ context.input.estimated_amount >= 100000 }};',
            description="Forbid creating claims with estimated amount >= $100,000",
            validation_mode=agentcore_alpha.PolicyValidationMode.IGNORE_ALL_FINDINGS,
        )

        CfnOutput(self, "PolicyEngineArn", value=policy_engine.policy_engine_arn)

        # ======================================================================
        # AGENTCORE RUNTIME (dual-agent, Cognito auth, observability)
        # ======================================================================

        # CloudWatch log group for runtime observability
        runtime_log_group = logs.LogGroup(
            self,
            "RuntimeLogGroup",
            log_group_name="/aws/bedrock-agentcore/claims-agent",
            removal_policy=RemovalPolicy.DESTROY,
            retention=logs.RetentionDays.ONE_WEEK,
        )

        # Agent runtime artifact from local Dockerfile (built with Finch/Docker)
        agent_artifact = agentcore.AgentRuntimeArtifact.from_asset("../app/claimsagent")

        # Create runtime with Cognito auth + observability
        runtime = agentcore.Runtime(
            self,
            "ClaimsRuntime",
            runtime_name="claimsagent",
            description="Event-driven dual-agent claims processor with confidence-based routing",
            agent_runtime_artifact=agent_artifact,
            # Auth: Cognito protects who can invoke the agent (external callers)
            authorizer_configuration=agentcore.RuntimeAuthorizerConfiguration.using_cognito(
                user_pool,
                [app_client],
            ),
            # Observability
            tracing_enabled=True,
            logging_configs=[
                agentcore.LoggingConfig(
                    log_type=agentcore.LogType.APPLICATION_LOGS,
                    destination=agentcore.LoggingDestination.cloud_watch_logs(runtime_log_group),
                ),
            ],
            # Environment: pass gateway credentials for tool access
            environment_variables={
                "AGENTCORE_GATEWAY_URL": gateway.gateway_url,
                "AGENTCORE_GATEWAY_TOKEN_ENDPOINT": gateway.token_endpoint_url,
                "AGENTCORE_GATEWAY_OAUTH_SCOPES": ",".join(gateway.oauth_scopes) if gateway.oauth_scopes else "",
                "AGENTCORE_GATEWAY_CLIENT_ID": gateway.user_pool_client.user_pool_client_id,
                "AGENTCORE_GATEWAY_CLIENT_SECRET": gateway.user_pool_client.user_pool_client_secret.unsafe_unwrap(),
            },
        )

        # Grant runtime permission to invoke Bedrock model
        runtime.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
                resources=[
                    f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-sonnet-4-6",
                    "arn:aws:bedrock:*::foundation-model/anthropic.claude-sonnet-4-6",
                    "arn:aws:bedrock:*:*:inference-profile/*",
                ],
            )
        )

        # Grant runtime permission to invoke the gateway (workload identity)
        gateway.grant_invoke(runtime.role)

        # Grant runtime permission to access memory
        # (will be added after memory construct below)

        CfnOutput(self, "RuntimeArn", value=runtime.agent_runtime_arn)

        # ======================================================================
        # AGENTCORE MEMORY (SEMANTIC + SUMMARIZATION)
        # ======================================================================

        memory = agentcore.Memory(
            self,
            "ClaimsMemory",
            memory_name="claims_memory_cdk_v3",
            description="Long-term memory for claims agent conversations",
            expiration_duration=Duration.days(90),
            memory_strategies=[
                agentcore.MemoryStrategy.using_built_in_semantic(),
                agentcore.MemoryStrategy.using_built_in_summarization(),
            ],
        )

        CfnOutput(self, "MemoryId", value=memory.memory_id)

        # ======================================================================
        # AGENTCORE ONLINE EVALUATION (built-in + custom LLM-as-judge)
        # ======================================================================

        # Custom evaluator: Claims quality assessment
        _claims_evaluator = agentcore.Evaluator(
            self,
            "ClaimsQualityEvaluator",
            evaluator_name="claims_quality",
            level=agentcore.EvaluationLevel.SESSION,
            description="Evaluates claims processing quality including decision accuracy and routing correctness",
            evaluator_config=agentcore.EvaluatorConfig.llm_as_a_judge(
                instructions="Given the following agent session context:\n\n{context}\n\nTool calls made:\n{actual_tool_trajectory}\n\nEvaluate the claims agent response for: 1) correct policy lookup, 2) accurate coverage assessment, 3) appropriate confidence scoring, 4) correct routing decision (auto-approve vs human review). Rate the overall claims processing quality.",
                model_id="global.anthropic.claude-sonnet-4-6",
                rating_scale=agentcore.EvaluatorRatingScale.numerical(
                    [
                        agentcore.NumericalRatingOption(label="Poor", definition="Major errors in processing", value=1),
                        agentcore.NumericalRatingOption(
                            label="Below Average", definition="Some errors or missing steps", value=2
                        ),
                        agentcore.NumericalRatingOption(
                            label="Average", definition="Correct but could be more thorough", value=3
                        ),
                        agentcore.NumericalRatingOption(
                            label="Good", definition="Accurate processing with clear reasoning", value=4
                        ),
                        agentcore.NumericalRatingOption(
                            label="Excellent", definition="Perfect processing with comprehensive analysis", value=5
                        ),
                    ]
                ),
            ),
        )

        # Online evaluation config using the runtime as data source
        _evaluation = agentcore.OnlineEvaluationConfig(
            self,
            "ClaimsEvaluation",
            online_evaluation_config_name="claims_evaluation",
            evaluators=[
                agentcore.EvaluatorSelector.builtin(agentcore.BuiltinEvaluator.HELPFULNESS),
                agentcore.EvaluatorSelector.builtin(agentcore.BuiltinEvaluator.CORRECTNESS),
                agentcore.EvaluatorSelector.builtin(agentcore.BuiltinEvaluator.TOOL_SELECTION_ACCURACY),
                # claims_evaluator uses reference inputs — only for on-demand evaluation, not online
            ],
            data_source=agentcore.DataSourceConfig.from_agent_runtime_endpoint(runtime),
            sampling_percentage=100,
        )

        # ======================================================================
        # TRIGGER LAMBDA (S3 → EventBridge → Lambda → Runtime)
        # ======================================================================

        trigger_fn = lambda_.Function(
            self,
            "TriggerFn",
            function_name="ClaimsAgent-Trigger",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset("../lambdas/trigger"),
            environment={
                "AGENTCORE_RUNTIME_ARN": runtime.agent_runtime_arn,
                "COGNITO_USER_POOL_ID": user_pool.user_pool_id,
                "COGNITO_CLIENT_ID": app_client.user_pool_client_id,
                "COGNITO_CLIENT_SECRET": app_client.user_pool_client_secret.unsafe_unwrap(),
                "COGNITO_TOKEN_ENDPOINT": f"https://{domain.domain_name}.auth.{self.region}.amazoncognito.com/oauth2/token",
            },
            timeout=Duration.seconds(60),
        )

        # Grant trigger Lambda permission to invoke the runtime
        runtime.grant_invoke(trigger_fn)
        inbox_bucket.grant_read(trigger_fn)

        # --- EventBridge Rule: S3 PutObject → Trigger Lambda ---
        events.Rule(
            self,
            "ClaimInboxRule",
            rule_name="ClaimsAgent-InboxTrigger",
            event_pattern=events.EventPattern(
                source=["aws.s3"],
                detail_type=["Object Created"],
                detail={
                    "bucket": {"name": [inbox_bucket.bucket_name]},
                    "object": {"key": [{"prefix": "claims-inbox/"}]},
                },
            ),
            targets=[targets.LambdaFunction(trigger_fn)],
        )
