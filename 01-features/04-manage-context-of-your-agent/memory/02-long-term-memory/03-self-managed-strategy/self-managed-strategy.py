"""Self-managed memory strategy — you own the extraction pipeline.

What you learn:
    - Configure `customMemoryStrategy` with `selfManagedConfiguration`
    - Set trigger conditions (messageBasedTrigger / tokenBasedTrigger /
      timeBasedTrigger)
    - Wire the SNS topic that AgentCore notifies when a trigger fires
    - Write extracted records back via `BatchCreateMemoryRecords`

Self-managed flow:
    1. AgentCore writes the conversation payload to your S3 bucket
       (the bucket that the memoryExecutionRoleArn can write to)
    2. AgentCore publishes a notification to your SNS topic
    3. Your subscriber (Lambda, ECS task, etc.) reads the payload from S3,
       runs your extraction + consolidation logic, and calls
       BatchCreateMemoryRecords / BatchUpdateMemoryRecords / BatchDeleteMemoryRecords
       to persist results.

This script focuses on (1) wiring the strategy correctly. The extraction
subscriber lives outside AgentCore — see the example in
`examples/single-agent/with-strands-agent/02-custom-hook/
culinary-assistant-self-managed-strategy/lambda_function.py`.

Three surfaces:
    python self-managed-strategy.py boto3
    python self-managed-strategy.py sdk    # documents the SDK gap
    python self-managed-strategy.py cli

Prerequisites:
    pip install boto3 bedrock-agentcore
    export AWS_REGION=us-east-1
    export MEMORY_EXECUTION_ROLE_ARN=arn:aws:iam::<acct>:role/<role>
    export PAYLOAD_BUCKET=my-agentcore-payload-bucket
    export TOPIC_ARN=arn:aws:sns:<region>:<acct>:agentcore-self-managed
"""

import os
import sys
import time
import uuid

REGION = os.getenv("AWS_REGION", "us-east-1")
NAMESPACE_TEMPLATE = "/users/{actorId}/custom/"


def _strategy(payload_bucket: str, topic_arn: str) -> dict:
    return {
        "customMemoryStrategy": {
            "name": "MyOwnExtractor",
            "description": "Custom extraction owned by my Lambda",
            "namespaces": [NAMESPACE_TEMPLATE],
            "configuration": {
                "selfManagedConfiguration": {
                    "invocationConfiguration": {
                        "payloadDeliveryBucketName": payload_bucket,
                        "topicArn": topic_arn,
                    },
                    "historicalContextWindowSize": 10,
                    "triggerConditions": [
                        {"messageBasedTrigger": {"messageCount": 6}},
                        {"tokenBasedTrigger": {"tokenCount": 4000}},
                        {"timeBasedTrigger": {"idleSessionTimeout": 300}},
                    ],
                }
            },
        }
    }


# === boto3 ============================================================
def run_with_boto3() -> None:
    import boto3

    role_arn = os.environ["MEMORY_EXECUTION_ROLE_ARN"]
    bucket = os.environ["PAYLOAD_BUCKET"]
    topic_arn = os.environ["TOPIC_ARN"]

    control = boto3.client("bedrock-agentcore-control", region_name=REGION)

    memory_id = control.create_memory(
        name=f"SelfManaged_{int(time.time())}",
        description="Self-managed extraction strategy (boto3)",
        eventExpiryDuration=30,
        memoryExecutionRoleArn=role_arn,
        memoryStrategies=[_strategy(bucket, topic_arn)],
    )["memory"]["id"]
    print(f"[boto3] Created memory {memory_id}")
    deadline = time.time() + 300
    while time.time() < deadline:
        if control.get_memory(memoryId=memory_id)["memory"]["status"] == "ACTIVE":
            break
        time.sleep(5)

    print(
        f"[boto3] Memory ready. Send events with CreateEvent; AgentCore delivers\n"
        f"        payloads to s3://{bucket}/ and notifies {topic_arn} when a\n"
        f"        trigger fires. Have your subscriber call BatchCreateMemoryRecords\n"
        f"        to persist extracted records.\n"
        f"        To clean up: control.delete_memory(memoryId={memory_id!r}, ...)"
    )


# === AgentCore SDK ====================================================
# MemoryClient.create_memory_and_wait does not expose memoryExecutionRoleArn
# and its `strategies=` shape is not validated against selfManagedConfiguration.
# Use the wrapped boto3 client (client.gmcp_client) for this — same call as
# the boto3 path. There is no batch-record helper on MemoryClient either, so
# the extraction subscriber must use boto3 BatchCreateMemoryRecords directly.
def run_with_sdk() -> None:
    print(
        "[sdk] Self-managed strategies are not exposed by MemoryClient helpers.\n"
        "      - CreateMemory: use the boto3 path (memoryExecutionRoleArn is required\n"
        "        and not available on create_memory_and_wait).\n"
        "      - Extraction subscriber: call boto3 batch_create_memory_records /\n"
        "        batch_update_memory_records / batch_delete_memory_records directly\n"
        "        from your Lambda. MemoryClient has no batch-record wrapper."
    )


# === AWS CLI ==========================================================
CLI_WALKTHROUGH = """\
# 1. Create the memory with a self-managed strategy. The role must allow
#    PutObject to the bucket and Publish to the topic.
aws bedrock-agentcore-control create-memory \\
  --region "$AWS_REGION" --name "SelfManagedCli-$(date +%s)" \\
  --event-expiry-duration 30 --client-token "$(uuidgen)" \\
  --memory-execution-role-arn "$MEMORY_EXECUTION_ROLE_ARN" \\
  --memory-strategies "[{
    \\"customMemoryStrategy\\": {
      \\"name\\": \\"MyOwnExtractor\\",
      \\"description\\": \\"Custom extraction owned by my Lambda\\",
      \\"namespaces\\": [\\"/users/{actorId}/custom/\\"],
      \\"configuration\\": {
        \\"selfManagedConfiguration\\": {
          \\"invocationConfiguration\\": {
            \\"payloadDeliveryBucketName\\": \\"$PAYLOAD_BUCKET\\",
            \\"topicArn\\": \\"$TOPIC_ARN\\"
          },
          \\"historicalContextWindowSize\\": 10,
          \\"triggerConditions\\": [
            {\\"messageBasedTrigger\\": {\\"messageCount\\": 6}},
            {\\"tokenBasedTrigger\\": {\\"tokenCount\\": 4000}},
            {\\"timeBasedTrigger\\": {\\"idleSessionTimeout\\": 300}}
          ]
        }
      }
    }
  }]"
export MEMORY_ID=<id>

# 2. Send events; AgentCore drops payloads to S3 and publishes to SNS.
aws bedrock-agentcore create-event \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --actor-id user-alex --session-id sess-cli \\
  --event-timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \\
  --payload '[{"conversational":{"role":"USER","content":{"text":"hello"}}}]'

# 3. Your subscriber writes records back via batch APIs:
aws bedrock-agentcore batch-create-memory-records \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --records '[{
    "namespace":"/users/user-alex/custom/",
    "content":{"text":"User likes Python"},
    "memoryStrategyId":"<strategy-id-from-create-memory-response>"
  }]'

# 4. Teardown
aws bedrock-agentcore-control delete-memory \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" --client-token "$(uuidgen)"
"""


def main() -> None:
    surface = sys.argv[1] if len(sys.argv) > 1 else "boto3"
    if surface == "boto3":
        run_with_boto3()
    elif surface == "sdk":
        run_with_sdk()
    elif surface == "cli":
        print(CLI_WALKTHROUGH)
    else:
        print(f"Unknown surface {surface!r}. Use boto3 | sdk | cli.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
