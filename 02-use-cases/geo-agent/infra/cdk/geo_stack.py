"""CDK Stack for GEO Edge Serving Infrastructure.

Creates: Amazon DynamoDB table (KMS-encrypted, PITR enabled), three AWS Lambda
functions (handler, generator, storage), Lambda Function URL with OAC,
Amazon CloudFront distribution with bot-routing CloudFront Function,
and all supporting resources (KMS key, SQS DLQ, S3 log bucket).
"""

import os
from pathlib import Path

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    CfnOutput,
    Fn,
    aws_dynamodb as dynamodb,
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_kms as kms,
    aws_sqs as sqs,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
)
from constructs import Construct

LAMBDA_CODE_PATH = str(Path(__file__).parent.parent / "lambda")


class GeoEdgeServingStack(Stack):
    """GEO Edge Serving infrastructure stack."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Context parameters
        table_name = self.node.try_get_context("table_name") or "geo-content"
        default_origin_host = self.node.try_get_context("default_origin_host") or ""
        agent_runtime_arn = self.node.try_get_context("agent_runtime_arn") or ""
        origin_verify_secret = self.node.try_get_context("origin_verify_secret") or ""
        create_distribution = self.node.try_get_context("create_distribution") or True

        # KMS Key for DynamoDB encryption
        table_key = kms.Key(
            self, "GeoTableKey",
            description="CMK for GEO DynamoDB table encryption",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY,
            alias=f"alias/{construct_id}-geo-table-key",
        )

        # DynamoDB Table
        table = dynamodb.Table(
            self, "GeoContentTable",
            table_name=table_name,
            partition_key=dynamodb.Attribute(
                name="url_path", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.CUSTOMER_MANAGED,
            encryption_key=table_key,
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            time_to_live_attribute="ttl",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # SQS Dead Letter Queue for async generator
        generator_dlq = sqs.Queue(
            self, "GeneratorDLQ",
            queue_name=f"{construct_id}-generator-dlq",
            retention_period=Duration.days(14),
        )

        # Lambda: geo-content-storage
        storage_fn = lambda_.Function(
            self, "GeoStorageFunction",
            function_name="geo-content-storage",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="geo_storage.handler",
            code=lambda_.Code.from_asset(LAMBDA_CODE_PATH),
            memory_size=128,
            timeout=Duration.seconds(30),
            reserved_concurrent_executions=50,
            tracing=lambda_.Tracing.ACTIVE,
            environment={
                "GEO_TABLE_NAME": table_name,
                "GEO_TTL_SECONDS": "86400",
            },
        )
        table.grant_read_write_data(storage_fn)
        table_key.grant_encrypt_decrypt(storage_fn)

        # Lambda: geo-content-generator (async)
        generator_fn = lambda_.Function(
            self, "GeoGeneratorFunction",
            function_name="geo-content-generator",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="geo_generator.handler",
            code=lambda_.Code.from_asset(LAMBDA_CODE_PATH),
            memory_size=512,
            timeout=Duration.seconds(120),
            reserved_concurrent_executions=10,
            tracing=lambda_.Tracing.ACTIVE,
            dead_letter_queue=generator_dlq,
            environment={
                "GEO_TABLE_NAME": table_name,
                "AGENT_RUNTIME_ARN": agent_runtime_arn,
                "AGENTCORE_REGION": self.region,
                "GEO_TTL_SECONDS": "86400",
            },
        )
        table.grant_read_write_data(generator_fn)
        table_key.grant_encrypt_decrypt(generator_fn)

        if agent_runtime_arn:
            generator_fn.add_to_role_policy(iam.PolicyStatement(
                actions=["bedrock-agentcore:InvokeAgentRuntime"],
                resources=[agent_runtime_arn, f"{agent_runtime_arn}/runtime-endpoint/*"],
            ))

        # Lambda: geo-content-handler
        handler_fn = lambda_.Function(
            self, "GeoContentFunction",
            function_name="geo-content-handler",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="geo_content_handler.handler",
            code=lambda_.Code.from_asset(LAMBDA_CODE_PATH),
            memory_size=256,
            timeout=Duration.seconds(90),
            reserved_concurrent_executions=100,
            tracing=lambda_.Tracing.ACTIVE,
            environment={
                "GEO_TABLE_NAME": table_name,
                "GENERATOR_FUNCTION_NAME": generator_fn.function_name,
                "DEFAULT_ORIGIN_HOST": default_origin_host,
                "AGENT_RUNTIME_ARN": agent_runtime_arn,
                "AGENTCORE_REGION": self.region,
                "ORIGIN_VERIFY_SECRET": origin_verify_secret,
                "GEO_TTL_SECONDS": "86400",
            },
        )
        table.grant_read_write_data(handler_fn)
        table_key.grant_encrypt_decrypt(handler_fn)
        generator_fn.grant_invoke(handler_fn)

        if agent_runtime_arn:
            handler_fn.add_to_role_policy(iam.PolicyStatement(
                actions=["bedrock-agentcore:InvokeAgentRuntime"],
                resources=[agent_runtime_arn, f"{agent_runtime_arn}/runtime-endpoint/*"],
            ))

        # Lambda Function URL (IAM auth for OAC)
        fn_url = handler_fn.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.AWS_IAM,
        )

        # Allow CloudFront to invoke via Function URL (OAC SigV4)
        handler_fn.add_permission(
            "CloudFrontInvokeFunctionUrl",
            principal=iam.ServicePrincipal("cloudfront.amazonaws.com"),
            action="lambda:InvokeFunctionUrl",
            source_arn=f"arn:aws:cloudfront::{self.account}:distribution/*",
            function_url_auth_type=lambda_.FunctionUrlAuthType.AWS_IAM,
        )
        handler_fn.add_permission(
            "CloudFrontInvokeFunction",
            principal=iam.ServicePrincipal("cloudfront.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=f"arn:aws:cloudfront::{self.account}:distribution/*",
        )

        # OAC for Lambda Function URL
        oac = cloudfront.CfnOriginAccessControl(
            self, "GeoLambdaOac",
            origin_access_control_config=cloudfront.CfnOriginAccessControl.OriginAccessControlConfigProperty(
                name="geo-lambda-oac",
                description="OAC for GEO Lambda Function URL (SigV4)",
                signing_protocol="sigv4",
                signing_behavior="always",
                origin_access_control_origin_type="lambda",
            ),
        )

        # CloudFront Distribution (optional)
        if create_distribution and default_origin_host:
            self._create_distribution(
                default_origin_host, origin_verify_secret, fn_url, oac, handler_fn
            )

        # Outputs
        CfnOutput(self, "TableName", value=table.table_name)
        CfnOutput(self, "HandlerFunctionName", value=handler_fn.function_name)
        CfnOutput(self, "GeneratorFunctionName", value=generator_fn.function_name)
        CfnOutput(self, "StorageFunctionName", value=storage_fn.function_name)
        CfnOutput(self, "FunctionUrl", value=fn_url.url)
        CfnOutput(self, "OacId", value=oac.attr_id)

    def _create_distribution(self, origin_host, verify_secret, fn_url, oac, handler_fn):
        """Create an Amazon CloudFront distribution with bot-routing CFF."""

        # S3 bucket for access logs
        log_bucket = s3.Bucket(
            self, "DistributionLogBucket",
            bucket_name=f"geo-cf-logs-{self.account}-{self.stack_name.lower()}",
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_PREFERRED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            lifecycle_rules=[s3.LifecycleRule(expiration=Duration.days(90))],
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # CloudFront Function for bot detection
        cff_code = self._build_cff_code(origin_host)
        bot_router = cloudfront.Function(
            self, "GeoBotRouter",
            function_name=f"{self.stack_name}-geo-bot-router",
            code=cloudfront.FunctionCode.from_inline(cff_code),
            runtime=cloudfront.FunctionRuntime.JS_2_0,
            comment=f"GEO bot router for {origin_host}",
        )

        # Cache policy
        cache_policy = cloudfront.CachePolicy(
            self, "GeoCachePolicy",
            cache_policy_name=f"{self.stack_name}-geo-cache",
            default_ttl=Duration.seconds(0),
            max_ttl=Duration.days(1),
            min_ttl=Duration.seconds(0),
            enable_accept_encoding_gzip=True,
            enable_accept_encoding_brotli=True,
            header_behavior=cloudfront.CacheHeaderBehavior.allow_list(
                "x-geo-bot", "x-original-host"
            ),
            query_string_behavior=cloudfront.CacheQueryStringBehavior.allow_list(
                "action", "mode", "purge", "ua"
            ),
            cookie_behavior=cloudfront.CacheCookieBehavior.none(),
        )

        # Origin request policy
        origin_request_policy = cloudfront.OriginRequestPolicy(
            self, "GeoOriginRequestPolicy",
            origin_request_policy_name=f"{self.stack_name}-geo-origin-req",
            header_behavior=cloudfront.OriginRequestHeaderBehavior.allow_list(
                "x-geo-bot", "x-geo-bot-ua", "x-original-host", "x-origin-verify"
            ),
            query_string_behavior=cloudfront.OriginRequestQueryStringBehavior.all(),
            cookie_behavior=cloudfront.OriginRequestCookieBehavior.none(),
        )

        # Distribution using L1 construct for full OAC control
        fn_url_domain = Fn.select(2, Fn.split("/", fn_url.url))

        distribution = cloudfront.CfnDistribution(
            self, "GeoDistribution",
            distribution_config=cloudfront.CfnDistribution.DistributionConfigProperty(
                enabled=True,
                comment=f"GEO Edge Serving - {origin_host}",
                http_version="http2and3",
                price_class="PriceClass_All",
                viewer_certificate=cloudfront.CfnDistribution.ViewerCertificateProperty(
                    cloud_front_default_certificate=True,
                    minimum_protocol_version="TLSv1.2_2021",
                ),
                logging=cloudfront.CfnDistribution.LoggingProperty(
                    bucket=log_bucket.bucket_domain_name,
                    include_cookies=False,
                    prefix="cf-logs/",
                ),
                origins=[
                    cloudfront.CfnDistribution.OriginProperty(
                        id=origin_host,
                        domain_name=origin_host,
                        custom_origin_config=cloudfront.CfnDistribution.CustomOriginConfigProperty(
                            http_port=80,
                            https_port=443,
                            origin_protocol_policy="https-only",
                            origin_ssl_protocols=["TLSv1.2"],
                            origin_read_timeout=30,
                            origin_keepalive_timeout=5,
                        ),
                    ),
                    cloudfront.CfnDistribution.OriginProperty(
                        id="geo-lambda-origin",
                        domain_name=fn_url_domain,
                        origin_access_control_id=oac.attr_id,
                        custom_origin_config=cloudfront.CfnDistribution.CustomOriginConfigProperty(
                            http_port=80,
                            https_port=443,
                            origin_protocol_policy="https-only",
                            origin_ssl_protocols=["TLSv1.2"],
                            origin_read_timeout=85,
                            origin_keepalive_timeout=5,
                        ),
                        origin_custom_headers=[
                            cloudfront.CfnDistribution.OriginCustomHeaderProperty(
                                header_name="x-origin-verify",
                                header_value=verify_secret,
                            ),
                        ],
                    ),
                ],
                default_cache_behavior=cloudfront.CfnDistribution.DefaultCacheBehaviorProperty(
                    target_origin_id=origin_host,
                    viewer_protocol_policy="redirect-to-https",
                    allowed_methods=["GET", "HEAD", "OPTIONS"],
                    cached_methods=["GET", "HEAD"],
                    compress=True,
                    cache_policy_id=cache_policy.cache_policy_id,
                    origin_request_policy_id=origin_request_policy.origin_request_policy_id,
                    function_associations=[
                        cloudfront.CfnDistribution.FunctionAssociationProperty(
                            event_type="viewer-request",
                            function_arn=bot_router.function_arn,
                        ),
                    ],
                ),
            ),
        )

        CfnOutput(self, "DistributionId", value=distribution.ref)
        CfnOutput(self, "DistributionDomain", value=distribution.attr_domain_name)

    def _build_cff_code(self, origin_host: str) -> str:
        """Build the CloudFront Function code with the origin host baked in."""
        return f"""import cf from 'cloudfront';
var AI_BOT_PATTERNS = [
  'gptbot','oai-searchbot','chatgpt-user',
  'claudebot','claude-web','claude-user',
  'perplexitybot','perplexity-user',
  'google-extended','googleother',
  'bingbot','copilot',
  'meta-externalagent','facebookbot',
  'applebot','applebot-extended',
  'cohere-ai','amazonbot','bytespider','ccbot','diffbot','youbot'
];
function handler(event) {{
  var request = event.request;
  var ua = (request.headers['user-agent'] && request.headers['user-agent'].value) || '';
  var uaLower = ua.toLowerCase();
  var isAiBot = false;
  for (var i = 0; i < AI_BOT_PATTERNS.length; i++) {{
    if (uaLower.indexOf(AI_BOT_PATTERNS[i]) !== -1) {{ isAiBot = true; break; }}
  }}
  if (!isAiBot && request.querystring && request.querystring.ua && request.querystring.ua.value === 'genaibot') {{
    isAiBot = true;
  }}
  if (isAiBot) {{
    request.headers['x-geo-bot'] = {{ value: 'true' }};
    request.headers['x-geo-bot-ua'] = {{ value: ua }};
    request.headers['x-original-host'] = {{ value: '{origin_host}' }};
    cf.selectRequestOriginById('geo-lambda-origin');
  }}
  return request;
}}"""
