# Braintrust Setup Guide

## Overview

This guide provides comprehensive instructions for configuring Braintrust for the Simple Dual Observability Tutorial. Braintrust is an AI-focused observability platform that provides LLM-specific metrics, cost tracking, and quality evaluations.

## What is Braintrust?

Braintrust is a platform designed specifically for AI and LLM observability:

- **AI-First Metrics**: Token usage, cost tracking, quality scores
- **Prompt Management**: Version control and A/B testing for prompts
- **Evaluation Framework**: Automated quality and hallucination detection
- **OTEL Native**: Receives OpenTelemetry traces natively
- **Free Tier**: Generous free tier with unlimited traces (7-day retention)

## Prerequisites

Before setting up Braintrust:

1. Email address for account creation
2. Browser access to Braintrust web UI
3. OTEL collector configuration (included in tutorial)

## Account Creation

### Step 1: Sign Up for Free Account

1. Navigate to https://www.braintrust.dev/signup
2. Sign up using:
   - Email and password
   - Google account (SSO)
   - GitHub account (SSO)
3. Verify your email address (if using email signup)
4. Complete onboarding questionnaire (optional)

**Free Tier Includes**:
- Unlimited traces (7-day retention)
- Unlimited projects
- All core features
- Community support

### Step 2: Access Dashboard

After signup:

1. Log in to https://www.braintrust.dev/app
2. You will see the main dashboard
3. Click "Create Project" to get started

## API Key Management

### Generate API Key

1. Navigate to Settings: https://www.braintrust.dev/app/settings/api
2. Click "Create API Key"
3. Provide a name: "AgentCore-Observability-Demo"
4. Select permissions:
   - Read/Write access to traces
   - Read access to projects
5. Click "Generate"
6. **Copy and save the API key immediately** (shown only once)

**API Key Format**: `bt-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### Store API Key Securely

**Option 1: Environment Variable**

```bash
# Add to .env file
echo "BRAINTRUST_API_KEY=bt-xxxxx" >> .env

# Or export directly
export BRAINTRUST_API_KEY=bt-xxxxx
```

**Option 2: OTEL Collector Config**

The API key is used in `config/otel_config.yaml`:

```yaml
exporters:
  otlp/braintrust:
    endpoint: https://api.braintrust.dev/otel
    headers:
      Authorization: Bearer ${BRAINTRUST_API_KEY}
```

**Security Best Practices**:
- Never commit API keys to git
- Use environment variables or secrets management
- Rotate keys periodically
- Use separate keys for dev/prod

### Revoke API Key

If key is compromised:

1. Go to Settings > API Keys
2. Find the key by name or partial value
3. Click "Revoke"
4. Generate new key and update configuration

## Project Setup

### Create Project

1. From dashboard, click "Create Project"
2. Project name: `agentcore-observability-demo`
3. Description: "Simple dual observability tutorial for Amazon Bedrock AgentCore"
4. Click "Create"

### Configure Project Settings

1. Navigate to project settings (gear icon)
2. Configure retention:
   - Free tier: 7 days (default)
   - Paid tier: 30+ days (optional upgrade)
3. Set project metadata:
   - Environment: development
   - Owner: your email
   - Tags: agentcore, tutorial, observability

### Enable Features

Enable optional features for enhanced observability:

1. **Evaluations**: Automated quality checks
2. **Datasets**: Store test data for comparisons
3. **Experiments**: A/B testing for prompts
4. **Monitoring**: Real-time alerting (paid feature)

## OTEL Configuration

### Configure OTEL Collector

The tutorial includes pre-configured OTEL settings in `config/otel_config.yaml`:

```yaml
exporters:
  otlp/braintrust:
    endpoint: https://api.braintrust.dev/otel
    headers:
      Authorization: Bearer ${BRAINTRUST_API_KEY}
    tls:
      insecure: false
    compression: gzip
    timeout: 30s
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 30s
      max_elapsed_time: 300s

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, resource, batch]
      exporters: [otlp/braintrust, awsemf, logging]
```

### Verify Configuration

Test OTEL export to Braintrust:

```bash
# Set API key
export BRAINTRUST_API_KEY=bt-xxxxx

# Run automated setup (includes verification)
cd scripts
./setup_braintrust.sh --api-key $BRAINTRUST_API_KEY

# Or test manually with sample trace
curl -X POST https://api.braintrust.dev/otel/v1/traces \
  -H "Authorization: Bearer $BRAINTRUST_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "resourceSpans": [{
      "resource": {
        "attributes": [
          {"key": "service.name", "value": {"stringValue": "test"}}
        ]
      },
      "scopeSpans": []
    }]
  }'
```

Expected response: `200 OK`

## Dashboard Configuration

### Access Project Dashboard

1. Navigate to https://www.braintrust.dev/app
2. Select your project: `agentcore-observability-demo`
3. You will see tabs: Traces, Experiments, Datasets, Evaluations

### Understanding the Dashboard

**Traces Tab**:
- Lists all received traces
- Search by trace ID, session ID, or attributes
- Filter by time range, status, or custom fields
- Sort by latency, cost, or timestamp

**Key Metrics Displayed**:
- Total traces received
- Average latency
- Token usage (input/output)
- Estimated costs
- Error rate

### Viewing Traces

After running the demo, traces appear automatically:

1. Go to Traces tab
2. Find trace by ID (printed by demo script)
3. Click trace to open detail view

**Trace Detail View Shows**:
- Timeline visualization
- Span hierarchy
- Token consumption per span
- Cost breakdown
- Custom attributes
- Error details (if any)

### Search and Filter

**Search by Trace ID**:
```
trace_id = "1-67891011-abcdef1234567890"
```

**Search by Session**:
```
session_id = "demo_session_abc123"
```

**Search by Model**:
```
model_id CONTAINS "haiku"
```

**Filter by Time Range**:
- Last 5 minutes
- Last hour
- Last 24 hours
- Custom range

**Filter by Status**:
- Successful only
- Errors only
- All statuses

### Custom Views

Create custom views for specific use cases:

1. Click "Create View"
2. Name: "High Latency Traces"
3. Filter: `latency_ms > 2000`
4. Save view
5. Share with team (optional)

## Trace Visualization

### Timeline View

The timeline shows:
- Horizontal bars for span duration
- Color coding by span type:
  - Blue: LLM calls
  - Green: Tool executions
  - Red: Errors
  - Gray: Other operations
- Parent-child relationships
- Timing overlaps

### Token Usage View

View token consumption:
- Input tokens per span
- Output tokens per span
- Total tokens for trace
- Token usage over time (dashboard)

### Cost Analysis View

Braintrust automatically calculates costs:
- Cost per model call
- Cost per trace
- Daily/weekly cost trends
- Cost by agent or session

**Cost Calculation**:
```
Input cost = input_tokens × input_price_per_1k
Output cost = output_tokens × output_price_per_1k
Total cost = input_cost + output_cost
```

For Claude 3.5 Haiku:
- Input: $0.80 per 1M tokens
- Output: $4.00 per 1M tokens

## Evaluations

### Create Evaluation

Braintrust can automatically evaluate LLM responses:

1. Go to Evaluations tab
2. Click "Create Evaluation"
3. Select evaluation type:
   - **Factuality**: Check for hallucinations
   - **Relevance**: Response matches query
   - **Coherence**: Response is well-structured
   - **Custom**: Define your own criteria

4. Configure evaluation:
   - Model: Claude 3.5 Sonnet (for evaluation)
   - Criteria: Define what "good" means
   - Threshold: Minimum acceptable score

5. Run on existing traces or new traces

### View Evaluation Results

After evaluation runs:
- Overall score (0-100)
- Per-trace scores
- Failure reasons
- Improvement suggestions

## Alerts and Monitoring

### Set Up Alerts (Paid Feature)

For production monitoring, configure alerts:

1. Go to Monitoring tab
2. Click "Create Alert"
3. Define conditions:
   - High error rate (>5%)
   - High latency (P99 > 3s)
   - High cost (>$1/hour)
   - Low quality score (<80)

4. Configure notification:
   - Email
   - Slack
   - PagerDuty
   - Webhook

## Data Export

### Export Traces

Export traces for analysis:

1. Go to Traces tab
2. Select traces to export
3. Click "Export"
4. Choose format:
   - CSV
   - JSON
   - Parquet

### API Access

Access data programmatically:

```python
import requests

api_key = "bt-xxxxx"
project_id = "agentcore-observability-demo"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# Get recent traces
response = requests.get(
    f"https://api.braintrust.dev/v1/projects/{project_id}/traces",
    headers=headers,
    params={"limit": 100}
)

traces = response.json()
```

## Integration with Tutorial

### Automated Setup

The tutorial provides automated Braintrust setup:

```bash
cd scripts
./setup_braintrust.sh --api-key bt-xxxxx
```

This script:
1. Verifies API key
2. Creates project if not exists
3. Configures OTEL collector
4. Tests trace export
5. Generates usage guide

### Manual Integration

If setting up manually:

```bash
# 1. Set API key
export BRAINTRUST_API_KEY=bt-xxxxx

# 2. Update OTEL config
# Edit config/otel_config.yaml and replace ${BRAINTRUST_API_KEY}

# 3. Run demo
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario all

# 4. View traces in Braintrust dashboard
# https://www.braintrust.dev/app/projects/agentcore-observability-demo/traces
```

## Comparison with CloudWatch

### When to Use Braintrust

**Braintrust Strengths**:
- AI-specific metrics (quality, hallucination)
- Automatic cost calculation
- Better visualizations for LLM traces
- Prompt version comparison
- Evaluation framework

**Best For**:
- LLM quality monitoring
- Cost optimization
- Prompt engineering
- AI product development

### When to Use CloudWatch

**CloudWatch Strengths**:
- Native AWS integration
- CloudWatch Alarms
- Longer retention
- VPC integration
- AWS compliance requirements

**Best For**:
- Infrastructure monitoring
- AWS-native workflows
- Long-term storage
- Regulatory compliance

### Use Both

The dual export strategy provides best of both worlds:
- CloudWatch for infrastructure and compliance
- Braintrust for AI-specific insights
- Same OTEL traces in both platforms
- No vendor lock-in

## Troubleshooting

### API Key Issues

**Problem**: 401 Unauthorized error

**Solutions**:
1. Verify API key is correct
2. Check key is not revoked
3. Ensure key has proper permissions
4. Regenerate key if needed

### Traces Not Appearing

**Problem**: No traces in Braintrust dashboard

**Solutions**:
1. Verify API key is set: `echo $BRAINTRUST_API_KEY`
2. Check OTEL config references correct endpoint
3. Verify project name matches
4. Check network connectivity to braintrust.dev
5. Review OTEL collector logs for export errors

### Incomplete Trace Data

**Problem**: Traces missing spans or attributes

**Solutions**:
1. Verify OTEL config includes all processors
2. Check attribute size limits (max 1000 chars)
3. Ensure sampling rate is 1.0 (100%)
4. Review OTEL collector memory limits

### High Latency

**Problem**: Slow trace export to Braintrust

**Solutions**:
1. Enable compression in OTEL config (gzip)
2. Increase batch size
3. Check network latency to Braintrust API
4. Use async export mode

## Cost Management

### Free Tier Limits

Braintrust free tier includes:
- Unlimited traces
- 7-day retention
- All core features
- Community support

**No overage charges** - stays free forever.

### Upgrading to Paid Tier

For production needs:

**Pro Tier** ($50/month):
- 30-day retention
- Priority support
- Advanced evaluations
- Team collaboration

**Enterprise Tier** (custom):
- Custom retention
- SSO/SAML
- Dedicated support
- Custom SLAs

## Verification

After setup, verify Braintrust integration:

```bash
# 1. Test API key
curl -H "Authorization: Bearer $BRAINTRUST_API_KEY" \
  https://api.braintrust.dev/v1/auth/verify

# 2. Run demo
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario success

# 3. Check Braintrust dashboard
# Navigate to https://www.braintrust.dev/app/projects/agentcore-observability-demo

# 4. Verify trace appears
# Look for trace ID printed by demo script

# 5. Check token and cost data
# Verify token counts and cost calculations are present
```

## Next Steps

After Braintrust setup:

1. Run demo scenarios and explore traces
2. Create custom evaluations for your use case
3. Set up alerts for production monitoring (if using paid tier)
4. Compare CloudWatch and Braintrust trace views
5. Review [Troubleshooting Guide](troubleshooting.md) for common issues
