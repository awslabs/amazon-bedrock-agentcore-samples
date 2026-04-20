"""Messaging construct for SQS queues"""

from constructs import Construct
from aws_cdk import Duration, RemovalPolicy, aws_sqs as sqs, aws_iam as iam


class MessagingConstruct(Construct):
    """Construct for SQS queues used in the application."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        account_id: str,
        region: str,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Dead-letter queue for failed messages
        self.usage_dlq = sqs.Queue(
            self,
            "TokenUsageDLQ",
            queue_name=f"token-usage-dlq-{account_id}-{region}",
            retention_period=Duration.days(14),
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Token usage queue with DLQ
        self.usage_queue = sqs.Queue(
            self,
            "TokenUsageQueue",
            queue_name=f"token-usage-queue-{account_id}-{region}",
            visibility_timeout=Duration.seconds(300),
            retention_period=Duration.days(1),
            removal_policy=RemovalPolicy.DESTROY,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=self.usage_dlq,
            ),
        )

        # Enforce SSL/TLS on main queue
        self.usage_queue.add_to_resource_policy(
            iam.PolicyStatement(
                sid="EnforceSSLOnly",
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["sqs:*"],
                resources=[self.usage_queue.queue_arn],
                conditions={"Bool": {"aws:SecureTransport": "false"}},
            )
        )

        # Enforce SSL/TLS on DLQ
        self.usage_dlq.add_to_resource_policy(
            iam.PolicyStatement(
                sid="EnforceSSLOnly",
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["sqs:*"],
                resources=[self.usage_dlq.queue_arn],
                conditions={"Bool": {"aws:SecureTransport": "false"}},
            )
        )
