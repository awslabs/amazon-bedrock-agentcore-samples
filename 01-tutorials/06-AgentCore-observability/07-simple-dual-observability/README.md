# Simple Dual Platform Observability Tutorial

## Overview

This tutorial demonstrates Amazon Bedrock AgentCore's automatic OpenTelemetry instrumentation with dual platform export, sending traces to both AWS-native CloudWatch and AI-focused partner platform Braintrust simultaneously. The tutorial shows how AgentCore Runtime provides zero-code observability for agents, exporting traces to multiple platforms in parallel using standard OTEL format.

### Use case details
| Information         | Details                                                                                                                             |
|---------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| Use case type       | observability, monitoring                                                                                                           |
| Agent type          | Single agent with tools                                                                                                             |
| Use case components | AgentCore Runtime, AgentCore Gateway, MCP tools, OTEL dual export                                                                  |
| Use case vertical   | DevOps, Platform Engineering, AI Operations                                                                                        |
| Example complexity  | Intermediate                                                                                                                        |
| SDK used            | Amazon Bedrock AgentCore Runtime, boto3, OpenTelemetry                                                                             |

## Assets

| Asset | Description |
|-------|-------------|
| CloudWatch Dashboard | Pre-configured dashboard showing agent metrics, latency, and error rates |
| Braintrust Project | AI-focused observability with LLM cost tracking and quality metrics |
| Sample Agent | Weather, time, and calculator tools demonstrating tool execution tracing |

### Use case Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  TUTORIAL ARCHITECTURE                                          │
│                                                                 │
│  Your Laptop                                                    │
│    ↓ (runs simple_observability.py)                            │
│  Python CLI Script (boto3 client)                              │
│    ↓ (API call: invoke_agent)                                  │
│  AgentCore Runtime (Managed Service)                           │
│    ↓ (automatic OTEL instrumentation)                          │
│  Weather/Time Agent (deployed to Runtime)                      │
│    ↓ (tool calls routed through Gateway)                       │
│  AgentCore Gateway (Managed Service)                           │
│    ↓ (MCP protocol)                                            │
│  MCP Tools (weather, time, calculator)                         │
│    ↓ (traces exported automatically)                           │
│                                                                 │
│  ┌──────────────────┬─────────────────┐                        │
│  │ CloudWatch X-Ray │  Braintrust     │                        │
│  │ (AWS-native)     │  (AI platform)  │                        │
│  └──────────────────┴─────────────────┘                        │
│                                                                 │
│  Key: No Lambda functions required                             │
│       Zero code changes for observability                      │
│       Vendor-neutral OTEL format                               │
└─────────────────────────────────────────────────────────────────┘
```

### Use case key Features

- **Automatic OTEL Instrumentation**: AgentCore Runtime automatically generates OpenTelemetry traces with zero code changes
- **Dual Platform Export**: Simultaneous trace export to CloudWatch X-Ray and Braintrust using vendor-neutral OTEL format
- **Managed Services**: No Lambda functions or infrastructure management required
- **MCP Tool Integration**: Tools exposed via AgentCore Gateway using Model Context Protocol
- **Comprehensive Tracing**: Captures agent invocation, model calls, tool selection, and execution spans
- **Platform Comparison**: Demonstrates AWS-native vs AI-focused observability capabilities

## Detailed Documentation

For comprehensive information about this observability tutorial, please refer to the following detailed documentation:

- **[System Design](docs/DESIGN.md)** - Architecture overview, component interactions, and OTEL flow diagrams
- **[CloudWatch Setup](docs/cloudwatch-setup.md)** - CloudWatch configuration, dashboards, X-Ray tracing, and log groups
- **[Braintrust Setup](docs/braintrust-setup.md)** - Braintrust account creation, API key management, and dashboard configuration
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues, solutions, and debugging techniques
- **[Development](docs/development.md)** - Local testing, code structure, and adding new tools

## Prerequisites

| Requirement | Description |
|-------------|-------------|
| Python 3.11+ and `uv` | Python runtime and package manager. Install uv: `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| AWS Account | Active AWS account with Bedrock access enabled in your region |
| AWS CLI | Configured with credentials. Verify: `aws sts get-caller-identity` |
| boto3 SDK | Python SDK for AWS. Installed automatically via uv |
| IAM Permissions | Required permissions for AgentCore Runtime, CloudWatch, and X-Ray (see below) |
| Braintrust Account | Free tier account for dual platform demo. Sign up at https://www.braintrust.dev/signup |
| Amazon Bedrock Access | Access to Claude 3.5 Haiku model in your region |

### Required IAM Permissions

Your IAM user or role needs permissions for:
- `bedrock-agentcore-runtime:InvokeAgent`
- `bedrock-agentcore:CreateAgent`
- `bedrock-agentcore:CreateGateway`
- `bedrock-agentcore:ConfigureObservability`
- `bedrock:InvokeModel` (for Claude)
- `cloudwatch:PutMetricData`
- `xray:PutTraceSegments`
- `logs:CreateLogGroup`
- `logs:CreateLogStream`
- `logs:PutLogEvents`

## Use case setup

### Step 1: Clone Repository and Install Dependencies

```bash
# Clone the repository
git clone https://github.com/awslabs/amazon-bedrock-agentcore-samples
cd amazon-bedrock-agentcore-samples/01-tutorials/06-AgentCore-observability/07-simple-dual-observability

# Install dependencies for local invocation
# Note: Agent dependencies (strands-agents, bedrock-agentcore) are in requirements.txt
# and will be installed automatically during deployment to AgentCore Runtime
pip install boto3 pytz pydantic

# Alternative: If you want to test the agent locally before deployment
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

```bash
# Create .env file
cp .env.example .env

# Edit .env with your configuration
# Required:
#   AWS_REGION=us-east-1
#   BRAINTRUST_API_KEY=your_api_key_here (get from https://www.braintrust.dev/app/settings/api)
#
# Optional:
#   AGENTCORE_AGENT_ID=<set-after-deployment>
```

### Step 3: Run Automated Setup

The automated setup script deploys the agent, configures CloudWatch, and sets up Braintrust integration:

```bash
# Complete setup with CloudWatch and Braintrust
cd scripts
./setup_all.sh --braintrust

# Or setup with CloudWatch only
./setup_all.sh

# Or provide Braintrust API key directly
./setup_all.sh --api-key bt-xxxxx
```

This script will:
1. Deploy the weather/time agent to AgentCore Runtime
2. Configure MCP tools via AgentCore Gateway
3. Set up CloudWatch dashboard and X-Ray tracing
4. Configure Braintrust integration (if requested)
5. Create all necessary AWS resources
6. Generate `.agent_id` file with your agent ID

### Step 4: Load Environment Configuration

```bash
# Load environment variables created by setup
source scripts/.env

# Or manually set agent ID if not using setup script
export AGENTCORE_AGENT_ID=<your-agent-id>
export AWS_REGION=us-east-1
export BRAINTRUST_API_KEY=<your-api-key>
```

### Manual Setup (Alternative)

If you prefer manual setup instead of the automated script, see detailed instructions in [docs/cloudwatch-setup.md](docs/cloudwatch-setup.md) and [docs/braintrust-setup.md](docs/braintrust-setup.md).

## Running the tutorial

The demo script provides three scenarios demonstrating different observability features.

### Run All Scenarios (Recommended)

Run all three scenarios sequentially with automatic delays between each:

```bash
# From tutorial root directory
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
- Clean trace with all spans visible in both platforms

**Scenario 2: Error Handling**

Demonstrates error propagation and handling through observability:

```bash
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario error
```

Query: "Calculate the factorial of -5"

Expected behavior:
- Agent selects calculator tool
- Tool returns error (invalid input for factorial)
- Error status recorded in spans
- Graceful error handling visible in traces

**Scenario 3: Dashboard Walkthrough**

Displays links and guidance for viewing dashboards:

```bash
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario dashboard
```

This scenario does not invoke the agent - it provides links and explains what to look for in CloudWatch and Braintrust dashboards.

### Additional Options

```bash
# Enable debug logging for detailed execution traces
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario all --debug

# Specify different AWS region
python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --region us-west-2 --scenario success

# Using environment variables only (no command-line args)
export AGENTCORE_AGENT_ID=abc123xyz
python simple_observability.py
```

## Expected Results

### CloudWatch X-Ray Traces

After running scenarios, view traces in CloudWatch X-Ray:

1. Open CloudWatch Console: https://console.aws.amazon.com/cloudwatch
2. Navigate to X-Ray > Traces
3. Filter by time range (last 5 minutes)
4. Search for trace IDs printed by the script

**What You'll See:**
- Agent invocation span (root span)
- Tool selection span (reasoning phase)
- Gateway execution spans (one per tool)
- Response formatting span
- Total latency and individual span durations
- Error spans highlighted in red (Scenario 2)
- Span attributes: model ID, token counts, tool names

### Braintrust Traces

View the same traces in Braintrust with AI-focused metrics:

1. Open Braintrust Dashboard: https://www.braintrust.dev/app
2. Navigate to your project: "agentcore-observability-demo"
3. View traces tab
4. Search for trace IDs from the script output

**What You'll See:**
- LLM call details (model, temperature, max tokens)
- Token consumption (input tokens, output tokens, total)
- Cost breakdown by operation (calculated per model pricing)
- Latency timeline with interactive visualization
- Tool execution details and parameters
- Error annotations with stack traces (Scenario 2)
- Custom attributes and events

### Platform Comparison

**CloudWatch Strengths:**
- Native AWS integration with other services
- CloudWatch Alarms for automated alerting
- VPC Flow Logs correlation
- Longer retention options (up to 10 years)
- Integration with AWS Systems Manager and AWS Config

**Braintrust Strengths:**
- AI-focused metrics (quality scores, hallucination detection)
- LLM cost tracking across providers
- Prompt version comparison and A/B testing
- Evaluation frameworks for quality assurance
- Specialized AI/ML visualizations and analytics

**Both Platforms:**
- Receive identical OTEL traces (vendor-neutral format)
- Real-time trace ingestion
- Query by trace ID or session ID
- Span-level detail with attributes
- Support for distributed tracing

## Cleanup

To avoid unnecessary AWS charges, delete all created resources:

### Automated Cleanup

```bash
# Run cleanup script from scripts directory
cd scripts
./cleanup.sh

# Or with force flag to skip confirmations
./cleanup.sh --force
```

### Manual Cleanup

If you prefer manual cleanup:

```bash
# Step 1: Delete AgentCore agent
aws bedrock-agentcore delete-agent --agent-id $AGENTCORE_AGENT_ID

# Step 2: Delete CloudWatch resources
aws logs delete-log-group --log-group-name /aws/agentcore/observability
aws cloudwatch delete-dashboards --dashboard-names AgentCore-Observability-Demo

# Step 3: Clean up Braintrust (via web UI)
# Navigate to https://www.braintrust.dev/app
# Delete project: "agentcore-observability-demo"
# Or keep for future use - free tier has no expiration

# Step 4: Remove local files
rm -f scripts/.agent_id scripts/.env
rm -f .env
```

## Cost Estimate

### AWS Costs

**AgentCore Runtime:**
- Free tier: 1,000 agent invocations per month
- After free tier: $0.002 per invocation
- This tutorial: ~3 invocations = FREE (within free tier)

**LLM Model (Claude 3.5 Haiku):**
- Input tokens: ~500 tokens per query = ~1,500 total
- Output tokens: ~200 tokens per response = ~600 total
- Cost per run: ~$0.01

**CloudWatch X-Ray:**
- Free tier: 100,000 traces per month
- After free tier: $5 per 1 million traces
- This tutorial: 3 traces = FREE (within free tier)

**CloudWatch Logs:**
- Free tier: 5 GB per month
- After free tier: $0.50 per GB
- This tutorial: <1 MB = FREE (within free tier)

**Total AWS Cost:** ~$0.01 per tutorial run (LLM charges only)

### Braintrust Costs

**Free Tier (Forever):**
- Unlimited traces
- Unlimited projects
- 7-day trace retention
- All core features included

**This Tutorial:** FREE (uses free tier)

### Total Cost Estimate

**First Run:** ~$0.01 (one-time setup + LLM)
**Subsequent Runs:** ~$0.01 per run (LLM only)
**Monthly Cost:** <$1.00 for occasional testing and learning

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

### Community
- AWS re:Post: https://repost.aws/
- Braintrust Discord: https://discord.gg/braintrust
- OpenTelemetry Slack: https://slack.cncf.io/

## Next Steps

After completing this tutorial, consider:

1. Experiment with custom MCP tools and observe their traces
2. Configure CloudWatch Alarms for error rate monitoring
3. Set up Braintrust evaluations for agent quality monitoring
4. Integrate observability into your production applications
5. Explore advanced OTEL features (custom spans, events, metrics)
6. Compare observability data across multiple platforms
7. Build custom dashboards tailored to your use case

## Disclaimer

The examples provided in this repository are for experimental and educational purposes only. They demonstrate concepts and techniques but are not intended for direct use in production environments without proper security hardening and testing. Make sure to have Amazon Bedrock Guardrails in place to protect against prompt injection and other security risks.
