# Simple Dual Platform Observability Tutorial

This tutorial demonstrates Amazon Bedrock AgentCore's automatic OpenTelemetry instrumentation with dual platform export, sending traces to both AWS-native CloudWatch and partner platform Braintrust simultaneously.

## Overview

Learn how AgentCore Runtime provides automatic OTEL tracing for agents with zero code changes, exporting traces to multiple observability platforms in parallel. This tutorial uses a simple Python CLI script to invoke a runtime-hosted agent and view the same traces in both CloudWatch X-Ray and Braintrust.

## Architecture

```
┌─────────────────┐
│  Python CLI     │
│  (this demo)    │
└────────┬────────┘
         │ boto3 API call
         ▼
┌─────────────────┐
│  AgentCore      │
│  Runtime        │ (automatic OTEL instrumentation)
│  (managed)      │
└────────┬────────┘
         │ tool execution
         ▼
┌─────────────────┐
│  AgentCore      │
│  Gateway        │ (managed)
│  + MCP Tools    │
└────────┬────────┘
         │ traces exported
         ▼
┌─────────────────────────────────────┐
│  CloudWatch X-Ray  │  Braintrust    │
│  (AWS-native)      │  (AI platform) │
└─────────────────────────────────────┘
```

**Key Points:**
- No Lambda functions required - agent runs in AgentCore Runtime (fully managed)
- No manual instrumentation - AgentCore automatically generates OpenTelemetry traces
- Vendor-neutral OTEL format enables dual platform export
- Same traces visible in both CloudWatch and Braintrust

## What You'll Learn

1. How to deploy an MCP-enabled agent to AgentCore Runtime
2. How to configure AgentCore Gateway with MCP tools (weather, time, calculator)
3. How to enable dual OTEL export to CloudWatch and Braintrust
4. How to invoke the agent and generate traces
5. How to analyze traces in both CloudWatch X-Ray and Braintrust
6. How to compare AWS-native and AI-focused observability features

## Prerequisites

### AWS Account Requirements
- AWS account with appropriate permissions
- Amazon Bedrock access enabled in your region
- Amazon Bedrock AgentCore Runtime access
- CloudWatch X-Ray and CloudWatch Logs enabled
- AWS credentials configured locally

### Braintrust Account
- Free tier Braintrust account
- Create account at: https://www.braintrust.dev/signup
- Generate API key from: https://www.braintrust.dev/app/settings/api

### Development Environment
- Python 3.11 or higher
- AWS CLI configured
- boto3 SDK installed

### Permissions Required
Your IAM user/role needs permissions for:
- `bedrock-agentcore-runtime:InvokeAgent`
- `bedrock-agentcore:CreateAgent`
- `bedrock-agentcore:CreateGateway`
- `bedrock-agentcore:ConfigureObservability`
- `cloudwatch:PutMetricData`
- `xray:PutTraceSegments`
- `logs:CreateLogGroup`
- `logs:CreateLogStream`
- `logs:PutLogEvents`

## Setup Instructions

### Step 1: Deploy Agent to AgentCore Runtime

1. Create agent configuration with your LLM model:

```bash
aws bedrock-agentcore create-agent \
  --agent-name "simple-observability-demo" \
  --model-id "us.anthropic.claude-haiku-4-5-20251001-v1:0" \
  --instructions "You are a helpful assistant with access to weather, time, and calculator tools." \
  --region us-east-1
```

2. Note the agent ID from the response:

```json
{
  "agentId": "abc123xyz"
}
```

3. Set the agent ID as an environment variable:

```bash
export AGENTCORE_AGENT_ID=abc123xyz
```

### Step 2: Configure AgentCore Gateway with MCP Tools

Configure the gateway with three MCP tool servers:

1. Weather Tool (OpenWeatherMap):

```bash
aws bedrock-agentcore add-mcp-server \
  --agent-id $AGENTCORE_AGENT_ID \
  --server-name "weather" \
  --server-config '{
    "type": "openweather",
    "apiKey": "YOUR_OPENWEATHER_API_KEY"
  }'
```

2. Time Tool (built-in):

```bash
aws bedrock-agentcore add-mcp-server \
  --agent-id $AGENTCORE_AGENT_ID \
  --server-name "time" \
  --server-config '{
    "type": "datetime",
    "timezone": "UTC"
  }'
```

3. Calculator Tool (built-in):

```bash
aws bedrock-agentcore add-mcp-server \
  --agent-id $AGENTCORE_AGENT_ID \
  --server-name "calculator" \
  --server-config '{
    "type": "calculator"
  }'
```

### Step 3: Configure OTEL Dual Export

Configure AgentCore to export traces to both CloudWatch and Braintrust:

1. Get your Braintrust API key from https://www.braintrust.dev/app/settings/api

2. Configure dual export:

```bash
aws bedrock-agentcore configure-observability \
  --agent-id $AGENTCORE_AGENT_ID \
  --config '{
    "exporters": [
      {
        "type": "cloudwatch",
        "enabled": true,
        "config": {
          "region": "us-east-1",
          "namespace": "AgentCore/Demo"
        }
      },
      {
        "type": "braintrust",
        "enabled": true,
        "config": {
          "apiKey": "YOUR_BRAINTRUST_API_KEY",
          "projectName": "agentcore-observability-demo"
        }
      }
    ],
    "tracing": {
      "samplingRate": 1.0,
      "includeAttributes": true,
      "includeEvents": true
    }
  }'
```

3. Verify configuration:

```bash
aws bedrock-agentcore describe-agent --agent-id $AGENTCORE_AGENT_ID
```

### Step 4: Install Python Dependencies

1. Install required packages:

```bash
pip install boto3 botocore
```

Or using uv (recommended):

```bash
uv pip install boto3 botocore
```

### Step 5: Set Environment Variables

Set all required environment variables:

```bash
# Required: AgentCore agent ID
export AGENTCORE_AGENT_ID=abc123xyz

# Optional: AWS region (defaults to us-east-1)
export AWS_REGION=us-east-1

# Optional: Braintrust API key (if not configured in Step 3)
export BRAINTRUST_API_KEY=your_api_key_here
```

Create a `.env` file for convenience:

```bash
cat > .env << 'EOF'
AGENTCORE_AGENT_ID=abc123xyz
AWS_REGION=us-east-1
BRAINTRUST_API_KEY=your_api_key_here
EOF
```

## Running the Tutorial

The demo script provides three scenarios demonstrating different observability features.

### Run All Scenarios (Recommended)

Run all three scenarios sequentially with automatic delays:

```bash
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario all
```

### Run Individual Scenarios

**Scenario 1: Successful Multi-Tool Query**

Demonstrates successful agent execution with multiple tool calls:

```bash
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario success
```

Query: "What's the weather in Seattle and what time is it there?"

Expected behavior:
- Agent selects two tools (weather + time)
- Both tools execute successfully
- Agent aggregates responses
- Clean trace with all spans visible

**Scenario 2: Error Handling**

Demonstrates error propagation and handling:

```bash
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario error
```

Query: "Calculate the factorial of -5"

Expected behavior:
- Agent selects calculator tool
- Tool returns error (invalid input)
- Error status recorded in spans
- Graceful error handling by agent

**Scenario 3: Dashboard Walkthrough**

Displays links and guidance for viewing dashboards:

```bash
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario dashboard
```

No agent invocation - just displays dashboard information.

### Using Environment Variables

Run without command-line arguments:

```bash
export AGENTCORE_AGENT_ID=abc123xyz
python simple_observability.py
```

### Enable Debug Logging

See detailed execution logs:

```bash
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario all --debug
```

## Expected Results

### CloudWatch X-Ray Traces

After running scenarios, view traces in CloudWatch X-Ray:

1. Open CloudWatch Console: https://console.aws.amazon.com/cloudwatch
2. Navigate to X-Ray > Traces
3. Filter by time range (last 5 minutes)
4. Search for trace IDs printed by the script

**What You'll See:**
- Agent invocation span (root)
- Tool selection span (reasoning phase)
- Gateway execution spans (one per tool)
- Response formatting span
- Total latency and span durations
- Error spans highlighted in red (Scenario 2)
- Span attributes: model, tokens, tool names

### Braintrust Traces

View the same traces in Braintrust:

1. Open Braintrust Dashboard: https://www.braintrust.dev/app
2. Navigate to your project: "agentcore-observability-demo"
3. View traces tab
4. Search for trace IDs from the script output

**What You'll See:**
- LLM call details (model, temperature, max tokens)
- Token consumption (input, output, total)
- Cost breakdown by operation
- Latency timeline
- Tool execution details
- Error annotations (Scenario 2)
- Custom attributes and events

### CloudWatch Dashboards

View aggregated metrics:

1. Navigate to CloudWatch > Dashboards
2. Look for "AgentCore-Demo" dashboard
3. Review metrics:
   - Request rate (requests/minute)
   - Latency distribution (P50, P90, P99)
   - Error rate by tool
   - Token consumption over time
   - Success rate by query type

### Braintrust Dashboard

View AI-specific metrics:

1. Open Braintrust project dashboard
2. Review metrics:
   - LLM performance (latency, tokens)
   - Token costs (input, output, total)
   - Quality scores (if evaluations configured)
   - Trace search and filtering
   - Error analysis and trends

### Platform Comparison

**CloudWatch Strengths:**
- Native AWS integration
- CloudWatch Alarms for alerting
- Integration with other AWS services
- Longer retention options
- VPC Flow Logs correlation

**Braintrust Strengths:**
- AI-focused metrics (quality, hallucination)
- LLM cost tracking
- Prompt version comparison
- Evaluation frameworks
- Specialized AI/ML visualizations

**Both Platforms:**
- Receive identical OTEL traces
- Vendor-neutral trace format
- Real-time trace ingestion
- Query by trace ID
- Span-level detail

## Troubleshooting

### Agent Not Found Error

**Error:** `Agent with ID 'abc123xyz' not found`

**Solution:**
- Verify agent ID is correct
- Check agent deployment status
- Ensure you're using the correct AWS region

```bash
aws bedrock-agentcore list-agents --region us-east-1
```

### Permission Denied Error

**Error:** `User is not authorized to perform: bedrock-agentcore-runtime:InvokeAgent`

**Solution:**
- Add required IAM permissions (see Prerequisites)
- Verify AWS credentials are configured
- Check IAM policy is attached to your user/role

### Traces Not Appearing in CloudWatch

**Issue:** No traces visible in CloudWatch X-Ray

**Solution:**
- Wait 2-3 minutes for trace propagation
- Verify CloudWatch X-Ray is enabled in your region
- Check sampling rate is set to 1.0 (100%)
- Review CloudWatch Logs for export errors

```bash
aws logs tail /aws/agentcore/observability --follow
```

### Traces Not Appearing in Braintrust

**Issue:** No traces visible in Braintrust dashboard

**Solution:**
- Verify Braintrust API key is valid
- Check project name matches configuration
- Review Braintrust export configuration
- Check network connectivity to braintrust.dev

### Tool Execution Failures

**Issue:** Tool returns errors or timeouts

**Solution:**
- Verify MCP server configurations
- Check API keys (OpenWeatherMap, etc.)
- Review tool-specific logs in CloudWatch
- Test tools individually via gateway

### High Latency

**Issue:** Agent responses take too long

**Solution:**
- Review trace spans to identify bottleneck
- Check LLM model selection (smaller models faster)
- Verify network connectivity
- Review tool execution times

## Cleanup

To avoid unnecessary charges, delete all created resources:

### Step 1: Delete Agent

```bash
aws bedrock-agentcore delete-agent --agent-id $AGENTCORE_AGENT_ID
```

### Step 2: Delete CloudWatch Resources

```bash
# Delete log groups
aws logs delete-log-group --log-group-name /aws/agentcore/observability

# Delete custom dashboards
aws cloudwatch delete-dashboards --dashboard-names AgentCore-Demo
```

### Step 3: Clean Up Braintrust

1. Open Braintrust dashboard
2. Navigate to project settings
3. Delete project: "agentcore-observability-demo"

Or keep for future use - free tier has no expiration.

### Step 4: Remove Environment Variables

```bash
unset AGENTCORE_AGENT_ID
unset AWS_REGION
unset BRAINTRUST_API_KEY

# Remove .env file if created
rm -f .env
```

## Cost Estimate

### AWS Costs

**AgentCore Runtime:**
- Free tier: 1,000 agent invocations per month
- After free tier: $0.002 per invocation
- This demo: ~3 invocations = FREE (within free tier)

**LLM Model (Claude 3.5 Sonnet):**
- Input tokens: ~500 tokens per query = ~1,500 total
- Output tokens: ~200 tokens per response = ~600 total
- Cost: ~$0.01 per demo run

**CloudWatch X-Ray:**
- Free tier: 100,000 traces per month
- After free tier: $5 per 1 million traces
- This demo: 3 traces = FREE (within free tier)

**CloudWatch Logs:**
- Free tier: 5 GB per month
- After free tier: $0.50 per GB
- This demo: <1 MB = FREE (within free tier)

**Total AWS Cost:** ~$0.01 per demo run (LLM only)

### Braintrust Costs

**Free Tier (Forever):**
- Unlimited traces
- Unlimited projects
- 7-day trace retention
- All core features

**Paid Tier (Optional):**
- $50/month for extended retention
- Advanced evaluations
- Team collaboration

**This Demo:** FREE (uses free tier)

### Total Cost Estimate

**First Run:** ~$0.01 (one-time setup + LLM)
**Subsequent Runs:** ~$0.01 per run (LLM only)
**Monthly Cost:** <$1.00 for occasional testing

## Additional Resources

### Documentation
- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [CloudWatch X-Ray Documentation](https://docs.aws.amazon.com/xray/latest/devguide/)
- [Braintrust Documentation](https://www.braintrust.dev/docs)
- [OpenTelemetry Specification](https://opentelemetry.io/docs/)

### Related Tutorials
- Tutorial 02: Self-Hosted Agent Observability
- Tutorial 05: Lambda AgentCore Invocation
- MCP Server Configuration Guide
- Advanced OTEL Configuration

### Community
- AWS re:Post: https://repost.aws/
- Braintrust Discord: https://discord.gg/braintrust
- OpenTelemetry Slack: https://slack.cncf.io/

## Next Steps

After completing this tutorial:

1. Experiment with custom MCP tools
2. Configure CloudWatch Alarms for error rates
3. Set up Braintrust evaluations for quality monitoring
4. Integrate with your application
5. Explore advanced OTEL features (custom spans, events)
6. Compare metrics across multiple platforms

## License

This project is licensed under the terms specified in the repository.
