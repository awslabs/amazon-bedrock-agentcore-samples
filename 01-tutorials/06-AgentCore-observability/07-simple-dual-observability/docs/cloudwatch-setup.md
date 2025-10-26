# CloudWatch Setup Guide

## Overview

This guide provides comprehensive instructions for configuring Amazon CloudWatch for the Simple Dual Observability Tutorial. CloudWatch provides AWS-native observability with X-Ray tracing, CloudWatch Logs, and CloudWatch Metrics.

## Prerequisites

Before setting up CloudWatch:

1. AWS account with appropriate permissions
2. AWS CLI configured with credentials
3. Amazon Bedrock AgentCore Runtime access
4. IAM permissions for CloudWatch and X-Ray

## Required IAM Permissions

Your IAM user or role must have these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData",
        "cloudwatch:PutDashboard",
        "cloudwatch:GetDashboard",
        "cloudwatch:DeleteDashboards",
        "cloudwatch:ListDashboards"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "xray:PutTraceSegments",
        "xray:PutTelemetryRecords",
        "xray:GetSamplingRules",
        "xray:GetSamplingTargets",
        "xray:GetTraceSummaries",
        "xray:GetTraceGraph"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams",
        "logs:FilterLogEvents",
        "logs:DeleteLogGroup"
      ],
      "Resource": "arn:aws:logs:*:*:log-group:/aws/agentcore/*"
    }
  ]
}
```

## Automated Setup

The easiest way to configure CloudWatch is using the automated setup script:

```bash
cd scripts
./setup_cloudwatch.sh --region us-east-1
```

This script will:
1. Create CloudWatch log groups
2. Configure X-Ray tracing
3. Create pre-built dashboard
4. Set up metric filters
5. Generate CloudWatch URLs file

For manual setup, continue with the sections below.

## Manual Setup Steps

### Step 1: Configure AgentCore Observability

Enable observability for your AgentCore Runtime agent:

```bash
# Set your agent ID
export AGENTCORE_AGENT_ID=<your-agent-id>
export AWS_REGION=us-east-1

# Configure observability
aws bedrock-agentcore configure-observability \
  --agent-id $AGENTCORE_AGENT_ID \
  --region $AWS_REGION \
  --config '{
    "exporters": [
      {
        "type": "cloudwatch",
        "enabled": true,
        "config": {
          "region": "us-east-1",
          "namespace": "AgentCore/Observability",
          "logGroupName": "/aws/agentcore/observability",
          "xrayEnabled": true
        }
      }
    ],
    "tracing": {
      "samplingRate": 1.0,
      "includeAttributes": true,
      "includeEvents": true,
      "maxSpanAttributeLength": 1000
    }
  }'
```

### Step 2: Create CloudWatch Log Groups

Create dedicated log groups for agent traces:

```bash
# Create main log group
aws logs create-log-group \
  --log-group-name /aws/agentcore/observability \
  --region $AWS_REGION

# Create trace-specific log group
aws logs create-log-group \
  --log-group-name /aws/agentcore/traces \
  --region $AWS_REGION

# Set retention policy (7 days for demo)
aws logs put-retention-policy \
  --log-group-name /aws/agentcore/observability \
  --retention-in-days 7 \
  --region $AWS_REGION

aws logs put-retention-policy \
  --log-group-name /aws/agentcore/traces \
  --retention-in-days 7 \
  --region $AWS_REGION
```

### Step 3: Configure X-Ray Sampling

Create X-Ray sampling rule for agent traces:

```bash
# Create sampling rule (100% sampling for demo)
aws xray create-sampling-rule \
  --region $AWS_REGION \
  --sampling-rule '{
    "RuleName": "AgentCore-Demo-Sampling",
    "Priority": 1000,
    "FixedRate": 1.0,
    "ReservoirSize": 1,
    "ServiceName": "agentcore-observability-demo",
    "ServiceType": "*",
    "Host": "*",
    "HTTPMethod": "*",
    "URLPath": "*",
    "Version": 1,
    "ResourceARN": "*",
    "Attributes": {}
  }'
```

### Step 4: Create CloudWatch Dashboard

Create a dashboard to visualize agent metrics:

```bash
# Create dashboard using JSON configuration
aws cloudwatch put-dashboard \
  --dashboard-name AgentCore-Observability-Demo \
  --region $AWS_REGION \
  --dashboard-body file://dashboards/cloudwatch-dashboard.json
```

**Dashboard Configuration** (dashboards/cloudwatch-dashboard.json):

The pre-configured dashboard includes:

1. **Agent Invocation Metrics**
   - Request rate (requests per minute)
   - Success rate percentage
   - Error rate percentage

2. **Latency Metrics**
   - P50, P90, P99 latencies
   - Average latency over time
   - Maximum latency

3. **Tool Execution Metrics**
   - Tool call count by tool name
   - Tool execution duration
   - Tool success vs error rate

4. **Token Usage Metrics**
   - Input tokens consumed
   - Output tokens generated
   - Total token usage over time

5. **Error Analysis**
   - Error count by error type
   - Recent error log entries
   - Error rate trend

### Step 5: Configure Metric Filters

Create metric filters to extract custom metrics from logs:

```bash
# Metric filter for agent invocations
aws logs put-metric-filter \
  --log-group-name /aws/agentcore/observability \
  --filter-name AgentInvocations \
  --filter-pattern '[time, request_id, event_type = "AgentInvocation", ...]' \
  --metric-transformations \
    metricName=AgentInvocations,\
    metricNamespace=AgentCore/Observability,\
    metricValue=1,\
    defaultValue=0 \
  --region $AWS_REGION

# Metric filter for errors
aws logs put-metric-filter \
  --log-group-name /aws/agentcore/observability \
  --filter-name AgentErrors \
  --filter-pattern '[time, request_id, level = ERROR, ...]' \
  --metric-transformations \
    metricName=AgentErrors,\
    metricNamespace=AgentCore/Observability,\
    metricValue=1,\
    defaultValue=0 \
  --region $AWS_REGION

# Metric filter for token usage
aws logs put-metric-filter \
  --log-group-name /aws/agentcore/observability \
  --filter-name TokenUsage \
  --filter-pattern '[time, request_id, event_type = "TokenUsage", tokens]' \
  --metric-transformations \
    metricName=TokensUsed,\
    metricNamespace=AgentCore/Observability,\
    metricValue='$tokens',\
    defaultValue=0 \
  --region $AWS_REGION
```

## Viewing Traces in CloudWatch X-Ray

### Access X-Ray Console

1. Open CloudWatch Console: https://console.aws.amazon.com/cloudwatch
2. Navigate to X-Ray > Traces
3. Select your region
4. Set time range to "Last 5 minutes"

### Understanding the Trace Map

The service map shows:
- **Nodes**: Services (AgentCore Runtime, Gateway, Tools)
- **Edges**: Request flow between services
- **Colors**: Health status (green = healthy, red = errors)
- **Numbers**: Request count and latency

### Viewing Individual Traces

To view a specific trace:

1. Find trace by ID (printed by demo script)
2. Click on trace to open detail view
3. Examine spans:
   - Root span: Agent invocation
   - Child spans: LLM calls, tool executions
   - Leaf spans: Individual tool operations

### Analyzing Trace Timeline

The timeline view shows:
- Span duration (horizontal bars)
- Parent-child relationships (indentation)
- Timing overlaps (parallel execution)
- Error indicators (red highlighting)

## Viewing Logs in CloudWatch Logs

### Access CloudWatch Logs

1. Navigate to CloudWatch > Logs > Log groups
2. Select `/aws/agentcore/observability`
3. Choose recent log stream
4. Review structured log entries

### Log Query Examples

**Find all invocations for a session**:
```
fields @timestamp, @message
| filter session_id = "demo_session_abc123"
| sort @timestamp desc
```

**Find errors in last hour**:
```
fields @timestamp, level, message
| filter level = "ERROR"
| filter @timestamp > ago(1h)
| sort @timestamp desc
```

**Calculate average latency**:
```
fields @timestamp, duration_ms
| filter event_type = "AgentInvocation"
| stats avg(duration_ms) as avg_latency by bin(5m)
```

**Find tool execution failures**:
```
fields @timestamp, tool_name, error_message
| filter event_type = "ToolExecution" and status = "ERROR"
| sort @timestamp desc
```

## CloudWatch Metrics

### Available Metrics

Navigate to CloudWatch > Metrics > All metrics > AgentCore/Observability:

1. **AgentInvocations**: Count of agent invocations
2. **AgentErrors**: Count of errors
3. **TokensUsed**: Total tokens consumed
4. **ToolExecutions**: Count of tool calls
5. **Latency**: Response time distribution

### Creating Custom Metrics

Add custom metrics from your code:

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

cloudwatch.put_metric_data(
    Namespace='AgentCore/Observability',
    MetricData=[
        {
            'MetricName': 'CustomMetric',
            'Value': 123.0,
            'Unit': 'Count',
            'Dimensions': [
                {
                    'Name': 'AgentId',
                    'Value': agent_id
                }
            ]
        }
    ]
)
```

## CloudWatch Alarms

### Create Error Rate Alarm

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name AgentCore-High-Error-Rate \
  --alarm-description "Alert when error rate exceeds 10%" \
  --metric-name AgentErrors \
  --namespace AgentCore/Observability \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --region $AWS_REGION
```

### Create Latency Alarm

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name AgentCore-High-Latency \
  --alarm-description "Alert when P99 latency exceeds 5 seconds" \
  --metric-name Latency \
  --namespace AgentCore/Observability \
  --statistic "p99" \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 5000 \
  --comparison-operator GreaterThanThreshold \
  --region $AWS_REGION
```

## Transaction Search

CloudWatch Transaction Search allows searching across traces:

### Enable Transaction Search

```bash
# Enable for your region
aws cloudwatch enable-transaction-insights \
  --region $AWS_REGION
```

### Search by Trace ID

```bash
aws xray get-trace-summaries \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --filter-expression 'id = "1-67891011-abcdef1234567890"' \
  --region $AWS_REGION
```

### Search by Attribute

```bash
aws xray get-trace-summaries \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date -u +%s) \
  --filter-expression 'annotation.agent_id = "abc123"' \
  --region $AWS_REGION
```

## Cost Optimization

### Reduce Log Retention

```bash
# Set shorter retention for non-production
aws logs put-retention-policy \
  --log-group-name /aws/agentcore/observability \
  --retention-in-days 1 \
  --region $AWS_REGION
```

### Reduce Sampling Rate

For high-volume production, reduce sampling:

```bash
# Update sampling to 10%
aws xray update-sampling-rule \
  --rule-name AgentCore-Demo-Sampling \
  --sampling-rule-update '{
    "FixedRate": 0.1
  }' \
  --region $AWS_REGION
```

### Enable Log Compression

```bash
# Configure log compression for storage savings
aws logs put-log-events \
  --log-group-name /aws/agentcore/observability \
  --log-stream-name demo \
  --compression gzip
```

## Troubleshooting

### Traces Not Appearing

**Problem**: No traces visible in X-Ray

**Solutions**:
1. Verify observability is configured: `aws bedrock-agentcore describe-agent --agent-id $AGENTCORE_AGENT_ID`
2. Check sampling rate is not 0
3. Verify IAM permissions for X-Ray
4. Wait 2-3 minutes for propagation

### Logs Not Appearing

**Problem**: No logs in CloudWatch Logs

**Solutions**:
1. Verify log group exists: `aws logs describe-log-groups --log-group-name-prefix /aws/agentcore`
2. Check IAM permissions for Logs
3. Verify agent is invoking successfully
4. Check log stream creation

### Dashboard Not Loading

**Problem**: Dashboard shows no data

**Solutions**:
1. Verify metrics exist: `aws cloudwatch list-metrics --namespace AgentCore/Observability`
2. Check time range is recent
3. Verify dashboard JSON is valid
4. Confirm metric filters are active

### High Costs

**Problem**: CloudWatch costs are high

**Solutions**:
1. Reduce log retention period
2. Decrease sampling rate
3. Use metric filters instead of querying logs
4. Enable log compression
5. Delete old log groups

## Verification

After setup, verify everything works:

```bash
# 1. Check log groups exist
aws logs describe-log-groups \
  --log-group-name-prefix /aws/agentcore \
  --region $AWS_REGION

# 2. Verify sampling rule
aws xray get-sampling-rules --region $AWS_REGION

# 3. Check dashboard exists
aws cloudwatch get-dashboard \
  --dashboard-name AgentCore-Observability-Demo \
  --region $AWS_REGION

# 4. List metric filters
aws logs describe-metric-filters \
  --log-group-name /aws/agentcore/observability \
  --region $AWS_REGION

# 5. Run demo and check for logs
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario success

# 6. Verify logs appeared
aws logs tail /aws/agentcore/observability --follow
```

## Next Steps

After CloudWatch setup:

1. Review [Braintrust Setup](braintrust-setup.md) for dual platform export
2. Run demo scenarios and explore traces
3. Customize dashboard for your use case
4. Set up CloudWatch Alarms for production monitoring
5. Review [Troubleshooting Guide](troubleshooting.md) for common issues
