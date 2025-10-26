# Create Simple Observability Demo with Dual Platform Support

## Overview

Create a new tutorial demonstrating Amazon Bedrock AgentCore observability using both AWS-native CloudWatch and partner platform Braintrust. This tutorial will show how AgentCore's OpenTelemetry instrumentation works with multiple observability backends.

**Architecture:** Simple CLI script → AgentCore Runtime (managed) → AgentCore Gateway (managed) → MCP Tools

**No Lambda required!** The agent runs in AgentCore Runtime, a fully managed service.

```
Your Laptop/EC2
    │
    │ simple_observability_demo.py
    │ (CLI script using boto3)
    ▼
AgentCore Runtime (Managed)
    │
    │ Your Strands Agent (hosted)
    │ Automatic OTEL instrumentation
    ▼
AgentCore Gateway (Managed)
    │
    ├─→ Weather MCP Tool
    ├─→ Time MCP Tool
    └─→ Calculator MCP Tool

    │
    └─→ CloudWatch X-Ray + Braintrust
        (OTEL traces exported automatically)
```

## Objective

Build a simple, standalone demo that shows:
1. Automatic OTEL tracing with AgentCore Runtime
2. Dual export to CloudWatch X-Ray and Braintrust
3. Side-by-side comparison of observability platforms
4. Error handling and debugging workflows
5. Production-ready patterns for observability configuration

## Scope

### New Tutorial Folder

Create: `01-tutorials/06-AgentCore-observability/07-simple-dual-observability-demo/`

### Components to Build

**1. Core Demo Script**
- `simple_observability_demo.py` (~150 lines)
  - Python CLI application using Strands agent framework
  - Deploy to AgentCore Runtime (managed hosting)
  - Integrate with AgentCore Gateway for 2-3 MCP tools (weather, time, calculator)
  - Configure dual OTEL export (CloudWatch + Braintrust)
  - Three demo scenarios: successful query, error handling, dashboard review
  - Clear logging with correlation IDs
  - Command-line argument parsing for flexible configuration

**2. Configuration Files**
- `config/otel_config.yaml`
  - CloudWatch OTEL endpoint configuration
  - Braintrust OTEL endpoint configuration
  - Sampling strategy
  - Resource attributes
  - Environment-based configuration support

**3. Dashboard Templates**
- `dashboards/cloudwatch-dashboard.json`
  - Pre-configured CloudWatch dashboard
  - Metrics: request rate, latency (P50/P90/P99), error rate, token usage
  - Widgets for trace visualization
  - Log insights queries

- `dashboards/braintrust-dashboard-export.json`
  - Braintrust dashboard configuration
  - AI-specific metrics: token costs, LLM performance, quality scores
  - Export format for easy import

**4. Demo Scenarios**
- `scenarios/demo_scenarios.md`
  - Scenario 1: Successful multi-tool query
  - Scenario 2: Error handling (invalid input)
  - Scenario 3: Dashboard walkthrough
  - Expected outputs for each scenario
  - CloudWatch and Braintrust views to examine
  - Timing estimates

**5. Deployment Scripts**
- `scripts/deploy_agent.sh`
  - Deploy Strands agent to AgentCore Runtime
  - Configure agent with tools
  - Set up OTEL environment variables
  - Verify deployment

- `scripts/setup_cloudwatch.sh`
  - Enable CloudWatch Transaction Search
  - Create CloudWatch dashboard
  - Configure log groups
  - Set up IAM permissions if needed

- `scripts/setup_braintrust.sh`
  - Braintrust project setup
  - Configure OTEL integration
  - Import dashboard template
  - Generate API key instructions

**6. Documentation**
- `README.md`
  - Overview and learning objectives
  - Prerequisites (AWS account, Braintrust free tier)
  - Step-by-step setup instructions
  - Running the demo
  - Expected results and screenshots
  - Troubleshooting section

- `docs/DEMO_GUIDE.md`
  - Detailed walkthrough for presentations
  - What to highlight in each scenario
  - Common questions and answers
  - Comparison: when to use CloudWatch vs Braintrust

## Technical Requirements

### Prerequisites
- Python 3.11+
- AWS account with Amazon Bedrock access
- Braintrust account (free tier)
- AgentCore Runtime access
- AgentCore Gateway deployed

### Dependencies
- `boto3` - AWS SDK
- `opentelemetry-sdk` - OTEL instrumentation
- `opentelemetry-exporter-otlp` - OTEL export
- Agent framework (Strands)
- Standard library: `argparse`, `logging`, `json`

### AWS Resources Required
- AgentCore Runtime agent deployment
- AgentCore Gateway with MCP tools
- CloudWatch Logs group
- CloudWatch dashboard
- X-Ray tracing enabled
- IAM role with appropriate permissions

### External Resources
- Braintrust free tier account (1M spans/month, no credit card required)

## Implementation Details

### Code Structure

```python
# simple_observability_demo.py structure

import argparse
import logging
import boto3
from opentelemetry import trace

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def setup_otel(cloudwatch_endpoint: str, braintrust_endpoint: str):
    """Configure OTEL with dual export."""
    pass


def invoke_agent(agent_id: str, query: str) -> dict:
    """Invoke AgentCore Runtime agent with tracing."""
    pass


def scenario_success():
    """Scenario 1: Successful multi-tool query."""
    pass


def scenario_error():
    """Scenario 2: Error handling demonstration."""
    pass


def scenario_dashboard():
    """Scenario 3: Dashboard walkthrough."""
    pass


def main():
    parser = argparse.ArgumentParser(description="...")
    # Add arguments
    args = parser.parse_args()

    # Setup OTEL
    setup_otel(args.cloudwatch_endpoint, args.braintrust_endpoint)

    # Run scenarios
    scenario_success()
    scenario_error()
    scenario_dashboard()


if __name__ == "__main__":
    main()
```

### OTEL Configuration Pattern

```yaml
# config/otel_config.yaml

exporters:
  cloudwatch:
    endpoint: "${CLOUDWATCH_OTEL_ENDPOINT}"
    region: "${AWS_REGION}"

  braintrust:
    endpoint: "${BRAINTRUST_OTEL_ENDPOINT}"
    headers:
      authorization: "Bearer ${BRAINTRUST_API_KEY}"

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [cloudwatch, braintrust]

resource:
  attributes:
    service.name: "simple-observability-demo"
    service.version: "1.0.0"
    deployment.environment: "demo"
```

### Demo Scenarios

**Scenario 1: Successful Query**
```
Query: "What's the weather in Seattle and what time is it there?"

Expected behavior:
- Agent selects weather and time tools
- Gateway executes both tool calls
- Response aggregates results
- Trace shows: agent → tool_selection → gateway → tool_1, tool_2
- Latency: ~1-2 seconds

CloudWatch view: X-Ray trace tree, CloudWatch Logs
Braintrust view: Trace timeline, token usage, LLM call details
```

**Scenario 2: Error Handling**
```
Query: "Calculate the factorial of -5"

Expected behavior:
- Agent selects calculator tool
- Tool returns error (negative input invalid)
- Error propagated through spans
- Agent handles gracefully
- Trace shows: agent → tool_selection → gateway → tool (ERROR)

CloudWatch view: Error span (red), error details in attributes
Braintrust view: Error in timeline, exception recorded
```

**Scenario 3: Dashboard Review**
```
Action: Open pre-configured dashboards

CloudWatch dashboard:
- Request rate (requests/minute)
- Latency distribution (P50, P90, P99)
- Error rate by tool
- Token consumption over time

Braintrust dashboard:
- LLM performance metrics
- Token costs
- Quality scores (if evaluated)
- Trace search and filtering
```

## Acceptance Criteria

- [ ] All files created in correct folder structure
- [ ] Python script runs without errors
- [ ] Traces appear in both CloudWatch and Braintrust
- [ ] Same trace_id visible in both platforms
- [ ] All three scenarios execute successfully
- [ ] CloudWatch dashboard shows metrics
- [ ] Braintrust dashboard shows traces
- [ ] README has clear setup instructions
- [ ] Deployment scripts work end-to-end
- [ ] Code follows Python best practices (type hints, logging, error handling)
- [ ] Documentation includes troubleshooting section
- [ ] No hardcoded credentials or secrets

## Testing Checklist

- [ ] Fresh environment setup (validate instructions work)
- [ ] Deploy agent to AgentCore Runtime successfully
- [ ] Configure OTEL dual export
- [ ] Run Scenario 1: verify successful trace in both platforms
- [ ] Run Scenario 2: verify error trace in both platforms
- [ ] Open CloudWatch dashboard: verify metrics visible
- [ ] Open Braintrust dashboard: verify traces visible
- [ ] Correlate trace_id between platforms
- [ ] Test with different queries
- [ ] Verify logging output is clear
- [ ] Test deployment scripts on clean AWS account
- [ ] Verify Braintrust free tier is sufficient

## Documentation Requirements

### README.md Must Include

1. **Overview**
   - What this demo shows
   - Learning objectives
   - Estimated time: 15-20 minutes

2. **Prerequisites**
   - AWS account requirements
   - Braintrust account signup (free tier)
   - Required permissions
   - Tools: Python 3.11+, AWS CLI, uv

3. **Setup Instructions**
   - Step 1: Clone repository
   - Step 2: Install dependencies
   - Step 3: Configure AWS credentials
   - Step 4: Sign up for Braintrust
   - Step 5: Deploy agent
   - Step 6: Configure OTEL
   - Step 7: Run demo

4. **Running the Demo**
   - Command-line usage
   - Environment variables
   - Expected output

5. **Expected Results**
   - Screenshots of CloudWatch traces
   - Screenshots of Braintrust traces
   - Dashboard examples

6. **Troubleshooting**
   - Common issues and solutions
   - How to verify OTEL configuration
   - Debugging tips

7. **Cleanup**
   - How to delete AWS resources
   - Cost considerations

### DEMO_GUIDE.md Must Include

1. **Presentation Flow**
   - Introduction (2 min)
   - Scenario 1 walkthrough (3 min)
   - Scenario 2 walkthrough (2 min)
   - Dashboard comparison (2 min)
   - Q&A prep (1 min)

2. **Key Points to Highlight**
   - AgentCore automatic instrumentation
   - OTEL vendor neutrality
   - CloudWatch vs Braintrust strengths
   - When to use each platform

3. **Demo Tips**
   - What to show in CloudWatch
   - What to show in Braintrust
   - How to correlate traces
   - Common questions and answers

## Dependencies and References

### Reusable Code Patterns From Existing Tutorials

**Note:** This demo does NOT use AWS Lambda. The agent runs in AgentCore Runtime (fully managed service). We reference the Lambda tutorial only for useful code patterns.

**Code patterns to reuse:**
- Error handling patterns from `05-Lambda-AgentCore-invocation/lambda_agentcore_invoker.py`
- OTEL configuration from `02-Agent-not-hosted-on-runtime/Strands/`
- Session tracking patterns from Lambda example
- Logging configuration from Lambda example

These patterns work in any Python code (Lambda or CLI script).

### External Documentation

- Amazon Bedrock AgentCore Observability: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-service-provided.html
- OpenTelemetry Python: https://opentelemetry.io/docs/languages/python/
- Braintrust Documentation: https://www.braintrust.dev/docs
- CloudWatch X-Ray: https://docs.aws.amazon.com/xray/

## Estimated Effort

- **Development:** 3 days
  - Day 1: Core script with CloudWatch integration
  - Day 2: Add Braintrust integration and dashboards
  - Day 3: Documentation, deployment scripts, testing

- **Testing:** 0.5 days
  - End-to-end testing
  - Fresh environment validation
  - Documentation review

- **Total:** 3.5 days

## Success Metrics

- Demo runs end-to-end in under 10 minutes
- Traces visible in both platforms with same trace_id
- Clear value proposition: "AgentCore works with your observability choice"
- Documentation enables users to replicate independently
- Code quality passes all linting and type checks

## Related Issues

None
