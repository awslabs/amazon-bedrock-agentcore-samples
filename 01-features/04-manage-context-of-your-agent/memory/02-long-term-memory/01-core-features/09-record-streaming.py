#!/usr/bin/env python

# # Streaming Memory Record Events with Amazon Bedrock AgentCore Memory
#
# ## Overview
#
# This tutorial demonstrates how to set up [**memory record streaming**](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-record-streaming.html) with Amazon Bedrock AgentCore Memory. You'll configure an [Amazon Kinesis Data Stream](https://docs.aws.amazon.com/streams/latest/dev/introduction.html) to receive real-time notifications when memory records are created, updated, or deleted — enabling event-driven architectures without polling APIs.
#
# ### Tutorial Details
#
# | Information         | Details                                                          |
# |:--------------------|:-----------------------------------------------------------------|
# | Tutorial type       | Memory Record Streaming                                          |
# | Feature             | Long-Term Memory Event Streaming                                 |
# | Key features        | Kinesis Data Streams, Memory Record Lifecycle Events             |
# | Example complexity  | Intermediate                                                     |
# | SDK used            | boto3                                                            |
#
# ### What You'll Learn
#
# In this tutorial, you'll learn how to:
# 1. Create an Amazon Kinesis Data Stream to receive memory record events
# 2. Set up an IAM role for AgentCore Memory to publish to your stream
# 3. Create a memory resource with streaming enabled
# 4. Trigger and consume memory record lifecycle events in real time
# 5. Configure event content levels (`FULL_CONTENT` or `METADATA_ONLY`)
#
# ### How It Works
#
# Memory record streaming uses a push-based delivery model. When memory records change, events are automatically published to your Kinesis Data Stream:
#
# - **MemoryRecordCreated** — Triggered by long-term memory extraction or `BatchCreateMemoryRecords` API
# - **MemoryRecordUpdated** — Triggered by `BatchUpdateMemoryRecords` API
# - **MemoryRecordDeleted** — Triggered by consolidation workflows, `DeleteMemoryRecord`, or `BatchDeleteMemoryRecords` API

# ### Architecture
#
# <div style="text-align:left">
#     <img src="memory_record_streaming.png" width="90%"/>
# </div>

# ## 0. Prerequisites
#
# To execute this tutorial you will need:
# * Python 3.10+
# * AWS credentials configured with access to AgentCore Memory, Kinesis, and IAM
# * Amazon Bedrock model access (for long-term memory extraction)
#
# First, let's install the required libraries:


# Run: pip install boto3>=1.42.63


# ### Setting Up Environment
#
# Let's import the required libraries and configure our environment:


import os
import json
import time
import uuid
import base64
import logging
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError

# Configuration
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("memory-streaming")

REGION = os.getenv("AWS_REGION", "us-west-2")
ACCOUNT_ID = boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]

# Initialize boto3 clients
kinesis_client = boto3.client("kinesis", region_name=REGION)
iam_client = boto3.client("iam")
agentcore_control_client = boto3.client("bedrock-agentcore-control", region_name=REGION)
agentcore_client = boto3.client("bedrock-agentcore", region_name=REGION)

# Unique identifier for resource naming
unique_id = str(uuid.uuid4())[:8]
print(f"Account: {ACCOUNT_ID}, Region: {REGION}, Unique ID: {unique_id}")


# ## 1. Create a Kinesis Data Stream
#
# First, we create a Kinesis Data Stream in your account. This is where AgentCore Memory will publish memory record lifecycle events.
#
# We use a single shard (supporting upto 1000 records/sec writes) which suffices for this tutorial. For production workloads please check [Resharding a Stream](https://docs.aws.amazon.com/streams/latest/dev/kinesis-using-sdk-java-resharding.html) to scale capacity.


stream_name = f"memory-record-stream-{unique_id}"

try:
    kinesis_client.create_stream(
        StreamName=stream_name,
        ShardCount=1,  # Single shard is sufficient for this tutorial
    )
    logger.info(f"Creating Kinesis stream: {stream_name}")

    # Wait for the stream to become active
    waiter = kinesis_client.get_waiter("stream_exists")
    waiter.wait(StreamName=stream_name)

    stream_info = kinesis_client.describe_stream(StreamName=stream_name)
    stream_arn = stream_info["StreamDescription"]["StreamARN"]
    print(f"Kinesis stream created: {stream_arn}")

except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceInUseException":
        stream_info = kinesis_client.describe_stream(StreamName=stream_name)
        stream_arn = stream_info["StreamDescription"]["StreamARN"]
        print(f"Stream already exists: {stream_arn}")
    else:
        raise


# ## 2. Create an IAM Role for Streaming
#
# AgentCore Memory needs an IAM role it can assume to publish events to your Kinesis Data Stream. This role requires:
# - A **trust policy** allowing `bedrock-agentcore.amazonaws.com` to assume the role
# - A **permissions policy** granting `kinesis:PutRecords` and `kinesis:DescribeStream` on your stream


role_name = f"AgentCoreMemoryStreamingRole-{unique_id}"

# Trust policy — allows AgentCore Memory to assume this role
trust_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "bedrock-agentcore.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}

# Permissions policy — scoped to our specific Kinesis stream
permissions_policy = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["kinesis:PutRecords", "kinesis:DescribeStream"],
            "Resource": stream_arn,
        }
    ],
}

try:
    # Create the IAM role
    create_role_response = iam_client.create_role(
        RoleName=role_name,
        AssumeRolePolicyDocument=json.dumps(trust_policy),
        Description="Allows AgentCore Memory to publish events to Kinesis",
    )
    role_arn = create_role_response["Role"]["Arn"]

    # Attach the inline permissions policy
    iam_client.put_role_policy(
        RoleName=role_name,
        PolicyName="KinesisPublishPolicy",
        PolicyDocument=json.dumps(permissions_policy),
    )

    # Allow time for IAM propagation
    print(f"IAM role created: {role_arn}")
    print("Waiting 10 seconds for IAM propagation...")
    time.sleep(10)

except ClientError as e:
    if e.response["Error"]["Code"] == "EntityAlreadyExists":
        role_arn = f"arn:aws:iam::{ACCOUNT_ID}:role/{role_name}"
        print(f"Role already exists: {role_arn}")
    else:
        raise


# ## 3. Create a Memory with Streaming Enabled
#
# Now we create an AgentCore Memory resource with a stream delivery configuration. The key parameters are:
#
# - **`streamDeliveryResources`** — Points to our Kinesis stream and specifies the content level
# - **`memoryExecutionRoleArn`** — The IAM role AgentCore will assume to publish events
# - **`FULL_CONTENT`** — Includes the memory record text in each event (use `METADATA_ONLY` for lightweight notifications)
#
# We also configure a long-term memory strategy (user preferences) so that conversation events get extracted into memory records, which in turn trigger streaming events.


memory_name = f"streaming_memory_{unique_id}"
actor_id = "demo-user"


def wait_for_memory_active(memory_id, timeout=250):
    """Poll GetMemory until the memory status is ACTIVE or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        resp = agentcore_control_client.get_memory(memoryId=memory_id)
        status = resp["memory"]["status"]
        print(f"  Memory status: {status}")
        if status == "ACTIVE":
            return resp["memory"]
        if status == "FAILED":
            raise RuntimeError(
                f"Memory creation failed: {resp['memory'].get('failureReason')}"
            )
        time.sleep(5)
    raise TimeoutError("Timed out waiting for memory to become ACTIVE")


try:
    response = agentcore_control_client.create_memory(
        name=memory_name,
        description="Memory with long-term memory record streaming enabled",
        eventExpiryDuration=7,
        memoryExecutionRoleArn=role_arn,
        memoryStrategies=[
            {
                "userPreferenceMemoryStrategy": {
                    "name": "UserPreferences",
                    "description": "Extracts user preferences, facts, and interests from conversations",
                    "namespaces": ["/{actorId}/user_preferences/"],
                }
            }
        ],
    )
    memory_id = response["memory"]["id"]
    print(f"Memory creation initiated: {memory_id}")
    print("Waiting for memory to become ACTIVE...")
    wait_for_memory_active(memory_id)
    print(f"Memory created with streaming enabled: {memory_id}")

except ClientError as e:
    logger.error(f"Error creating memory: {e}")
    raise


# ## 4. Verify Streaming Is Enabled
#
# When you create a memory with streaming, AgentCore Memory validates the configuration and publishes a `StreamingEnabled` event to your Kinesis stream. Let's read from the stream to confirm.


def read_kinesis_events(stream_name, max_wait_seconds=60, max_events=10):
    """Read events from a Kinesis Data Stream.

    Polls the stream for new records and decodes them.

    Args:
        stream_name: Name of the Kinesis stream
        max_wait_seconds: Maximum time to poll before returning
        max_events: Maximum number of events to collect

    Returns:
        List of decoded event payloads
    """
    events = []

    # Get a shard iterator starting from the oldest available record
    stream_info = kinesis_client.describe_stream(StreamName=stream_name)
    shard_id = stream_info["StreamDescription"]["Shards"][0]["ShardId"]

    iterator_response = kinesis_client.get_shard_iterator(
        StreamName=stream_name,
        ShardId=shard_id,
        ShardIteratorType="TRIM_HORIZON",  # to read from the oldest available record
    )
    shard_iterator = iterator_response["ShardIterator"]

    start_time = time.time()
    while time.time() - start_time < max_wait_seconds and len(events) < max_events:
        response = kinesis_client.get_records(ShardIterator=shard_iterator, Limit=100)

        for record in response["Records"]:
            data = (
                base64.b64decode(record["Data"])
                if isinstance(record["Data"], str)
                else record["Data"]
            )
            payload = json.loads(data)
            events.append(payload)

        shard_iterator = response["NextShardIterator"]

        if not response["Records"]:
            time.sleep(2)

    return events


# Check for the StreamingEnabled validation event
print("Checking for StreamingEnabled event...")
events = read_kinesis_events(stream_name, max_wait_seconds=30, max_events=1)

if events:
    for event in events:
        print(json.dumps(event, indent=2))
else:
    print(
        "No events received yet. The StreamingEnabled event may take a moment to arrive."
    )


# ## 5. Trigger Memory Record Events
#
# Now let's generate memory record lifecycle events by creating conversation data. We'll use two approaches:
#
# | Approach | API | How It Works |
# |:---------|:----|:-------------|
# | **Option A** | [`CreateEvent`](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_CreateEvent.html) | Send a conversation; AgentCore **asynchronously** extracts long-term records via the configured strategy |
# | **Option B** | [`BatchCreateMemoryRecords`](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_BatchCreateMemoryRecords.html) | Create records directly; events are published **immediately** |
#
# ### Option A: Create events via short-term memory (triggers async extraction)
#
# When you send conversation events, AgentCore Memory asynchronously extracts long-term memory records using the configured strategy. Each extracted record triggers a `MemoryRecordCreated` event on your stream.


# Send a conversation that contains extractable user preferences
agentcore_client.create_event(
    memoryId=memory_id,
    actorId=f"{actor_id}",
    sessionId="streaming-demo-session-001",
    eventTimestamp=datetime.now(timezone.utc),
    payload=[
        {
            "conversational": {
                "content": {
                    "text": "I went hiking yesterday. I really like hiking in the Pacific Northwest. I also enjoyed the Thai restaurant. Thai food is amazing."
                },
                "role": "USER",
            }
        },
        {
            "conversational": {
                "content": {
                    "text": "Great! I'll remember that you enjoy hiking in the Pacific Northwest and prefer Thai dining options."
                },
                "role": "ASSISTANT",
            }
        },
    ],
)

print(
    "Conversation event sent. Long-term memory extraction will happen asynchronously."
)


# ### Option B: Create memory records directly
#
# You can also create memory records directly using the `BatchCreateMemoryRecords` API. Each created record immediately triggers a `MemoryRecordCreated` event.


response = agentcore_client.batch_create_memory_records(
    memoryId=memory_id,
    records=[
        {
            "requestIdentifier": "direct-record-1",
            "content": {"text": "User prefers window seats on flights"},
            "namespaces": [f"/{actor_id}/user_preferences/"],
            "timestamp": str(int(time.time())),
        },
        {
            "requestIdentifier": "direct-record-2",
            "content": {"text": "User's favorite programming language is Python"},
            "namespaces": [f"/{actor_id}/user_preferences/"],
            "timestamp": str(int(time.time())),
        },
    ],
)

print(
    f"Batch created {len(response.get('successfulRecords', []))} memory records directly."
)
print(
    f"with record IDs: \n {[i.get('memoryRecordId') for i in response.get('successfulRecords', [])]}"
)


# ## 6. Consume Streaming Events
#
# Let's read from the Kinesis stream to see the memory record lifecycle events. Since long-term memory extraction is asynchronous, we'll poll for up to 90 seconds to allow time for processing.
#
#
# > **Production note:** In a real application, you could use an [AWS Lambda event source mapping](https://docs.aws.amazon.com/lambda/latest/dg/with-kinesis.html) or [Amazon Kinesis Client Library (KCL)](https://docs.aws.amazon.com/streams/latest/dev/shared-throughput-kcl-consumers.html) to consume the stream instead of polling.


print("Polling Kinesis stream for memory record events...\n")
events = read_kinesis_events(stream_name, max_wait_seconds=90, max_events=10)

print(f"Received {len(events)} event(s):\n")
for i, event in enumerate(events):
    stream_event = event.get("memoryStreamEvent", {})
    event_type = stream_event.get("eventType", "Unknown")
    event_time = stream_event.get("eventTime", "")
    record_id = stream_event.get("memoryRecordId", "N/A")
    record_text = stream_event.get("memoryRecordText", "")

    print(f"--- Event {i + 1}: {event_type} ---")
    print(f"  Time:      {event_time}")
    print(f"  Memory ID: {stream_event.get('memoryId', 'N/A')}")
    print(f"  Record ID: {record_id}")
    if record_text:
        print(f"  Content:   {record_text[:120]}...")
    print()


# ### Inspect full event payloads
#
# Let's look at the raw JSON of one event to see the complete schema:


if events:
    # Show full payload of the first MemoryRecordCreated event
    created_events = [
        e
        for e in events
        if e.get("memoryStreamEvent", {}).get("eventType") == "MemoryRecordCreated"
    ]
    if created_events:
        print("Full MemoryRecordCreated event payload:")
        print(json.dumps(created_events[0], indent=2))
    else:
        print("Full payload of first event:")
        print(json.dumps(events[0], indent=2))
else:
    print(
        "No events to inspect. Extraction may still be in progress — try re-running this cell."
    )


# ## 7. Cross-Reference with ListMemoryRecords
#
# Let's verify the streamed events match what's stored in memory by listing the records directly:


records_response = agentcore_client.list_memory_records(
    memoryId=memory_id, namespace=f"/{actor_id}/user_preferences/"
)

records = records_response.get("memoryRecordSummaries", [])
print(
    f"Found {len(records)} memory record(s) in namespace '/{actor_id}/user-preferences/':\n"
)

for record in records:
    print(f"  Record ID: {record['memoryRecordId']}")
    print(f"  Content:   {record.get('content', {}).get('text', 'N/A')[:120]}")
    print(f"  Created:   {record.get('createdAt', 'N/A')}")
    print()


# ## 8. Cleanup (Optional)
#
# When you're done experimenting, clean up the resources created in this tutorial:
#
# > **Cost note:** Kinesis Data Streams incur [hourly charges per shard](https://aws.amazon.com/kinesis/data-streams/pricing/). Be sure to delete the stream when you're finished to avoid ongoing costs.


# Delete the memory resource
try:
    agentcore_control_client.delete_memory(memoryId=memory_id)
    print(f"Deleting memory: {memory_id}")
    # Poll until deletion completes
    while True:
        try:
            resp = agentcore_control_client.get_memory(memoryId=memory_id)
            status = resp["memory"]["status"]
            print(f"  Memory status: {status}")
            if status == "DELETING":
                time.sleep(5)
            else:
                break
        except agentcore_control_client.exceptions.ResourceNotFoundException:
            print("  Memory deleted successfully.")
            break
except Exception as e:
    print(f"Error deleting memory: {e}")

# Delete the Kinesis stream
try:
    kinesis_client.delete_stream(StreamName=stream_name, EnforceConsumerDeletion=True)
    print(f"Deleted Kinesis stream: {stream_name}")
except Exception as e:
    print(f"Error deleting stream: {e}")

# Delete the IAM role (must remove inline policy first)
try:
    iam_client.delete_role_policy(RoleName=role_name, PolicyName="KinesisPublishPolicy")
    iam_client.delete_role(RoleName=role_name)
    print(f"Deleted IAM role: {role_name}")
except Exception as e:
    print(f"Error deleting IAM role: {e}")


# ## Conclusion
#
# In this tutorial, you set up end-to-end memory record streaming with Amazon Bedrock AgentCore Memory. You learned how to:
#
# 1. **Create a Kinesis Data Stream** to receive memory record lifecycle events
# 2. **Configure an IAM role** with least-privilege permissions for AgentCore to publish to your stream
# 3. **Create a memory resource** with streaming enabled and `FULL_CONTENT` delivery
# 4. **Trigger events** via both conversation extraction and direct record creation
# 5. **Consume and inspect** `MemoryRecordCreated` events from the stream in real time
#
# ### Next Steps
# To learn further how to use Agentcore memory streaming capability for better, you could try the following:
# - **Add a Lambda consumer** to process events automatically (see the [documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/userguide/memory-streaming.html) for an example)
# - **Switch to `METADATA_ONLY`** content level to reduce data transfer when you only need change notifications
# - **Set up CloudWatch alarms** on `StreamPublishingFailure` and `StreamUserError` metrics for production monitoring
# - **Build event-driven workflows** — sync memory records to a data lake on S3, trigger notifications, or update user profiles downstream
