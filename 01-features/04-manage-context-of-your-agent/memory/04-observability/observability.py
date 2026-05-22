"""Observability for AgentCore Memory.

What you learn:
    - Query CloudWatch metrics for memory operations under the
      AWS/Bedrock-AgentCore namespace
    - Read streaming health metrics: StreamPublishingSuccess,
      StreamPublishingFailure, StreamUserError
    - Set up CloudWatch alarms on streaming failures
    - Tail extraction-pipeline logs from your account log group

Memory observability covers two layers:
    1. Data-plane invocations (CreateEvent, RetrieveMemoryRecords, etc.) —
       Invocations / Latency / Errors per memory resource.
    2. Asynchronous ingestion (extraction + consolidation) — Invocations,
       Latency, Errors, NumberOfMemoryRecords per strategy + record streaming
       publish health.

Two surfaces:
    python observability.py boto3
    python observability.py cli

SDK note: CloudWatch metrics and Logs are not exposed by MemoryClient —
please use the boto3 `cloudwatch` and `logs` clients directly (shown below).

Prerequisites:
    pip install boto3
    export AWS_REGION=us-east-1
    export MEMORY_ARN=arn:aws:bedrock-agentcore:us-east-1:111122223333:memory/mem-abc
"""

import os
import sys
from datetime import datetime, timedelta, timezone

REGION = os.getenv("AWS_REGION", "us-east-1")


# === boto3 ============================================================
def run_with_boto3() -> None:
    import boto3

    memory_arn = os.environ.get("MEMORY_ARN")
    if not memory_arn:
        print("[boto3] Set MEMORY_ARN to your memory resource ARN.")
        return

    cw = boto3.client("cloudwatch", region_name=REGION)
    logs = boto3.client("logs", region_name=REGION)

    def get_metric_sum(metric_name: str, minutes: int = 60) -> float:
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=minutes)
        resp = cw.get_metric_statistics(
            Namespace="AWS/Bedrock-AgentCore",
            MetricName=metric_name,
            Dimensions=[
                {"Name": "Operation", "Value": "MemoryStreamEvent"},
                {"Name": "Resource", "Value": memory_arn},
            ],
            StartTime=start, EndTime=end,
            Period=300, Statistics=["Sum"], Unit="Count",
        )
        return sum(p["Sum"] for p in resp.get("Datapoints", []))

    print(f"[boto3] Streaming metrics for {memory_arn} (last hour):")
    for name in ("StreamPublishingSuccess", "StreamPublishingFailure", "StreamUserError"):
        print(f"  {name:30s} = {get_metric_sum(name)}")

    memory_id = memory_arn.rsplit("/", 1)[-1]
    log_group = f"/aws/bedrock-agentcore/memory/{memory_id}"
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = end_ms - 30 * 60 * 1000
    print(f"\n[boto3] Recent ingestion logs from {log_group}:")
    try:
        events = logs.filter_log_events(
            logGroupName=log_group, startTime=start_ms, endTime=end_ms
        )
        for evt in events.get("events", []):
            print(f"  {evt['timestamp']} {evt['message'].strip()}")
    except logs.exceptions.ResourceNotFoundException:
        print("  (log group not found — enable log delivery on the memory)")

    # Optional: alarm on StreamPublishingFailure (uncomment + set SNS_TOPIC_ARN)
    # sns_topic_arn = os.environ["SNS_TOPIC_ARN"]
    # cw.put_metric_alarm(
    #     AlarmName=f"AgentCoreMemory-StreamFailure-{memory_id}",
    #     MetricName="StreamPublishingFailure",
    #     Namespace="AWS/Bedrock-AgentCore",
    #     Dimensions=[
    #         {"Name": "Operation", "Value": "MemoryStreamEvent"},
    #         {"Name": "Resource", "Value": memory_arn},
    #     ],
    #     Statistic="Sum", Period=300, EvaluationPeriods=1,
    #     Threshold=0, ComparisonOperator="GreaterThanThreshold",
    #     TreatMissingData="notBreaching",
    #     AlarmActions=[sns_topic_arn],
    # )


# === AWS CLI ==========================================================
CLI_WALKTHROUGH = """\
# CloudWatch metrics: namespace AWS/Bedrock-AgentCore.
# Streaming health is dimensioned by Operation=MemoryStreamEvent + Resource=<memory ARN>.
export MEMORY_ARN=arn:aws:bedrock-agentcore:$AWS_REGION:<acct>:memory/mem-abc

# 1. Sum streaming successes over the last hour
aws cloudwatch get-metric-statistics --region "$AWS_REGION" \\
  --namespace "AWS/Bedrock-AgentCore" --metric-name "StreamPublishingSuccess" \\
  --dimensions Name=Operation,Value=MemoryStreamEvent Name=Resource,Value="$MEMORY_ARN" \\
  --statistics Sum --period 300 \\
  --start-time "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \\
  --end-time   "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# 2. Sum streaming failures (alarm on this in production)
aws cloudwatch get-metric-statistics --region "$AWS_REGION" \\
  --namespace "AWS/Bedrock-AgentCore" --metric-name "StreamPublishingFailure" \\
  --dimensions Name=Operation,Value=MemoryStreamEvent Name=Resource,Value="$MEMORY_ARN" \\
  --statistics Sum --period 300 \\
  --start-time "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ)" \\
  --end-time   "$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# 3. Alarm on any failure in a 5-minute window
aws cloudwatch put-metric-alarm --region "$AWS_REGION" \\
  --alarm-name "AgentCoreMemory-StreamFailure" \\
  --namespace "AWS/Bedrock-AgentCore" --metric-name "StreamPublishingFailure" \\
  --dimensions Name=Operation,Value=MemoryStreamEvent Name=Resource,Value="$MEMORY_ARN" \\
  --statistic Sum --period 300 --evaluation-periods 1 \\
  --threshold 0 --comparison-operator GreaterThanThreshold \\
  --treat-missing-data notBreaching \\
  --alarm-actions "$SNS_TOPIC_ARN"

# 4. Tail ingestion logs (log group format: /aws/bedrock-agentcore/memory/<memoryId>)
MEMORY_ID="${MEMORY_ARN##*/}"
aws logs tail "/aws/bedrock-agentcore/memory/$MEMORY_ID" \\
  --region "$AWS_REGION" --since 30m --follow
"""


def main() -> None:
    surface = sys.argv[1] if len(sys.argv) > 1 else "boto3"
    if surface == "boto3":
        run_with_boto3()
    elif surface == "cli":
        print(CLI_WALKTHROUGH)
    else:
        print(f"Unknown surface {surface!r}. Use boto3 | cli.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
