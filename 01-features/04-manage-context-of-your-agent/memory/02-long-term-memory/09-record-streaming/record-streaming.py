"""Memory record streaming to Amazon Kinesis Data Streams.

What you learn:
    - Create a Kinesis stream + IAM role AgentCore can assume
    - Configure `streamDeliveryResources` on CreateMemory
    - Trigger MemoryRecordCreated events via BatchCreateMemoryRecords
    - Read events from the stream and inspect their schema

Three surfaces:
    python record-streaming.py boto3
    python record-streaming.py sdk    # documents the SDK gap
    python record-streaming.py cli

SDK note: MemoryClient.create_memory_and_wait does not expose
streamDeliveryResources or memoryExecutionRoleArn. Use the wrapped boto3
client (`client.gmcp_client`) or boto3 directly.

Prerequisites:
    pip install boto3 bedrock-agentcore
    export AWS_REGION=us-west-2
"""

import base64
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone

REGION = os.getenv("AWS_REGION", "us-west-2")
ACTOR_ID = "demo-user"


def _trust_policy() -> str:
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }],
    })


def _permissions_policy(stream_arn: str) -> str:
    return json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Action": ["kinesis:PutRecords", "kinesis:DescribeStream"],
            "Resource": stream_arn,
        }],
    })


def _read_kinesis_events(kinesis, stream_name, max_wait_seconds=60, max_events=10):
    info = kinesis.describe_stream(StreamName=stream_name)
    shard_id = info["StreamDescription"]["Shards"][0]["ShardId"]
    iterator = kinesis.get_shard_iterator(
        StreamName=stream_name, ShardId=shard_id, ShardIteratorType="TRIM_HORIZON"
    )["ShardIterator"]

    events = []
    deadline = time.time() + max_wait_seconds
    while time.time() < deadline and len(events) < max_events:
        resp = kinesis.get_records(ShardIterator=iterator, Limit=100)
        for record in resp["Records"]:
            data = record["Data"]
            if isinstance(data, str):
                data = base64.b64decode(data)
            events.append(json.loads(data))
        iterator = resp["NextShardIterator"]
        if not resp["Records"]:
            time.sleep(2)
    return events


# === boto3 ============================================================
def run_with_boto3() -> None:
    import boto3

    unique = str(uuid.uuid4())[:8]
    account = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]
    kinesis = boto3.client("kinesis", region_name=REGION)
    iam = boto3.client("iam")
    control = boto3.client("bedrock-agentcore-control", region_name=REGION)
    data = boto3.client("bedrock-agentcore", region_name=REGION)

    # 1. Kinesis stream
    stream_name = f"memory-record-stream-{unique}"
    kinesis.create_stream(StreamName=stream_name, ShardCount=1)
    kinesis.get_waiter("stream_exists").wait(StreamName=stream_name)
    stream_arn = kinesis.describe_stream(StreamName=stream_name)["StreamDescription"]["StreamARN"]
    print(f"[boto3] Stream {stream_arn}")

    # 2. IAM role AgentCore can assume to publish to the stream
    role_name = f"AgentCoreMemoryStreamingRole-{unique}"
    role_arn = iam.create_role(
        RoleName=role_name, AssumeRolePolicyDocument=_trust_policy(),
        Description="Allows AgentCore Memory to publish events to Kinesis",
    )["Role"]["Arn"]
    iam.put_role_policy(
        RoleName=role_name, PolicyName="KinesisPublishPolicy",
        PolicyDocument=_permissions_policy(stream_arn),
    )
    print(f"[boto3] Role {role_arn}; sleeping 10s for IAM propagation")
    time.sleep(10)

    # 3. Memory with stream delivery wired in
    memory_id = control.create_memory(
        name=f"streaming_memory_{unique}",
        description="Memory with record streaming enabled",
        eventExpiryDuration=7,
        memoryExecutionRoleArn=role_arn,
        streamDeliveryResources=[{
            "kinesisStreamArn": stream_arn,
            "contentLevel": "FULL_CONTENT",
        }],
        memoryStrategies=[{
            "userPreferenceMemoryStrategy": {
                "name": "UserPreferences",
                "namespaces": [f"/{ACTOR_ID}/user_preferences/"],
            }
        }],
    )["memory"]["id"]
    print(f"[boto3] Memory {memory_id}")
    deadline = time.time() + 300
    while time.time() < deadline:
        if control.get_memory(memoryId=memory_id)["memory"]["status"] == "ACTIVE":
            break
        time.sleep(5)

    # 4. Trigger MemoryRecordCreated events directly (no extraction wait).
    data.batch_create_memory_records(
        memoryId=memory_id,
        records=[
            {"requestIdentifier": "rec-1", "namespaces": [f"/{ACTOR_ID}/user_preferences/"],
             "timestamp": str(int(time.time())),
             "content": {"text": "User prefers window seats on flights."}},
            {"requestIdentifier": "rec-2", "namespaces": [f"/{ACTOR_ID}/user_preferences/"],
             "timestamp": str(int(time.time())),
             "content": {"text": "User's favourite language is Python."}},
        ],
    )
    print("[boto3] Wrote 2 records — polling Kinesis for events...")

    events = _read_kinesis_events(kinesis, stream_name, max_wait_seconds=60, max_events=10)
    print(f"[boto3] Received {len(events)} stream event(s):")
    for e in events:
        evt = e.get("memoryStreamEvent", {})
        print(f"  - {evt.get('eventType')} @ {evt.get('eventTime')} | record={evt.get('memoryRecordId', 'N/A')}")

    # 5. Cleanup
    control.delete_memory(memoryId=memory_id, clientToken=str(uuid.uuid4()))
    kinesis.delete_stream(StreamName=stream_name, EnforceConsumerDeletion=True)
    iam.delete_role_policy(RoleName=role_name, PolicyName="KinesisPublishPolicy")
    iam.delete_role(RoleName=role_name)
    print("[boto3] Cleaned up memory, stream, role")


# === AgentCore SDK ====================================================
def run_with_sdk() -> None:
    print(
        "[sdk] Stream delivery is not exposed by MemoryClient.\n"
        "      - streamDeliveryResources: not on create_memory_and_wait\n"
        "      - memoryExecutionRoleArn: not on create_memory_and_wait\n"
        "      Use boto3 (see run_with_boto3) or:\n"
        "        client.gmcp_client.create_memory(\n"
        "            ..., streamDeliveryResources=[...],\n"
        "            memoryExecutionRoleArn=...)"
    )


# === AWS CLI ==========================================================
CLI_WALKTHROUGH = """\
# Prereqs: a Kinesis stream and an IAM role whose trust policy allows
# bedrock-agentcore.amazonaws.com to assume it, with kinesis:PutRecords +
# kinesis:DescribeStream on the stream ARN.
export STREAM_ARN=arn:aws:kinesis:$AWS_REGION:<acct>:stream/my-mem-stream
export ROLE_ARN=arn:aws:iam::<acct>:role/AgentCoreMemoryStreamingRole

# 1. Create memory with streaming enabled
aws bedrock-agentcore-control create-memory \\
  --region "$AWS_REGION" --name "StreamingCli-$(date +%s)" \\
  --event-expiry-duration 7 --client-token "$(uuidgen)" \\
  --memory-execution-role-arn "$ROLE_ARN" \\
  --stream-delivery-resources "[{
    \\"kinesisStreamArn\\": \\"$STREAM_ARN\\",
    \\"contentLevel\\": \\"FULL_CONTENT\\"
  }]" \\
  --memory-strategies '[{
    "userPreferenceMemoryStrategy": {
      "name":"UserPreferences",
      "namespaces":["/{actorId}/user_preferences/"]
    }
  }]'
export MEMORY_ID=<id>

# 2. Trigger events directly (no extraction wait)
aws bedrock-agentcore batch-create-memory-records \\
  --region "$AWS_REGION" --memory-id "$MEMORY_ID" \\
  --records '[{
    "requestIdentifier":"rec-1",
    "content":{"text":"User prefers window seats."},
    "namespaces":["/demo-user/user_preferences/"],
    "timestamp":"'"$(date +%s)"'"
  }]'

# 3. Read from Kinesis (production: use Lambda event source mapping or KCL).
SHARD=$(aws kinesis describe-stream --stream-name <name> \\
  --query 'StreamDescription.Shards[0].ShardId' --output text)
ITER=$(aws kinesis get-shard-iterator --stream-name <name> \\
  --shard-id "$SHARD" --shard-iterator-type TRIM_HORIZON \\
  --query 'ShardIterator' --output text)
aws kinesis get-records --shard-iterator "$ITER"

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
