# Simple Dual Platform Observability Tutorial

## Overview

This tutorial demonstrates Amazon Bedrock AgentCore's automatic OpenTelemetry instrumentation with flexible observability options:

1. **CloudWatch Observability (Default)**: Always enabled automatically with zero configuration
2. **Braintrust Observability (Optional)**: Add AI-focused observability with LLM metrics and cost tracking

The tutorial shows how AgentCore Runtime provides zero-code observability for agents deployed to the Runtime, with the option to export traces to Braintrust (an AI-focused observability platform) in addition to CloudWatch using standard OTEL format.

### Use case details
| Information         | Details                                                                                                                             |
|---------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| Use case type       | observability, monitoring                                                                                                           |
| Agent type          | Single agent with tools                                                                                                             |
| Use case components | AgentCore Runtime, Strands Agent, built-in tools, OTEL dual export                                                               |
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
│    ↓ (runs simple_observability.py or test_agent.sh)          │
│  Python CLI Script (boto3 client)                              │
│    ↓ (API call: invoke_agent)                                  │
│  AgentCore Runtime (Managed Service)                           │
│    ↓ (automatic OTEL instrumentation)                          │
│  Strands Agent (deployed to Runtime)                           │
│    ├─ Weather Tool (built-in)                                  │
│    ├─ Time Tool (built-in)                                     │
│    └─ Calculator Tool (built-in)                               │
│    ↓ (traces exported automatically)                           │
│                                                                 │
│  ┌──────────────────┬─────────────────┐                        │
│  │ CloudWatch Logs  │  Braintrust     │                        │
│  │ + X-Ray Traces   │  (AI platform)  │                        │
│  └──────────────────┴─────────────────┘                        │
│                                                                 │
│  Key: Zero code changes for observability                      │
│       Vendor-neutral OTEL format                               │
│       Fully managed agent hosting                              │
└─────────────────────────────────────────────────────────────────┘
```

### Use case key Features

- **Automatic OTEL Instrumentation**: AgentCore Runtime automatically generates OpenTelemetry traces with zero code changes
- **Dual Platform Export**: Simultaneous trace export to CloudWatch Logs/X-Ray and Braintrust using vendor-neutral OTEL format
- **Fully Managed**: AgentCore Runtime handles all infrastructure management and automatic instrumentation
- **Built-in Tools**: Strands agent with weather, time, and calculator tools for demonstration
- **Comprehensive Tracing**: Captures agent invocation, model calls, tool selection, and execution spans
- **Platform Comparison**: Demonstrates AWS-native vs AI-focused observability capabilities

## Detailed Documentation

For comprehensive information about this observability tutorial, please refer to the following detailed documentation:

### Observability Guides
- **[Observability Architecture](docs/observability-architecture.md)** - OTEL architecture, log types, trace correlation, and platform design
- **[Observability Options](docs/observability-options.md)** - Comparison of three deployment approaches and what each platform shows

### Setup and Configuration
- **[System Design](docs/design.md)** - Architecture overview, component interactions, and OTEL flow diagrams
- **[Braintrust Setup](docs/braintrust-setup.md)** - Braintrust account creation, API key management, and dashboard configuration

### Demonstrations and Development
- **[Demo Guide](scenarios/demo-guide.md)** - Step-by-step scenarios, presentation tips, and pre-demo checklist
- **[Troubleshooting](docs/troubleshooting.md)** - Common issues, solutions, and debugging techniques
- **[Development](docs/development.md)** - Local testing, code structure, and adding new tools

## Demo Videos

Watch these short videos to see the tutorial in action:

| Description | Video |
|---|---|
| **CloudWatch Metrics and Session Traces**<br>See how CloudWatch displays agent invocations, tool execution, and trace details in the GenAI Observability console.<br><br><details><summary>What you'll see:</summary><ul><li>Agent execution metrics (request count, latency, success rate)</li><li>Session traces with complete execution timeline</li><li>Tool calls and their individual latencies</li><li>Error handling and recovery</li></ul></details> | ▶️ **[Watch Video](https://github.com/user-attachments/assets/63c877e8-9611-4824-9aa4-7d1ae9ed9b1d)** |
| **CloudWatch APM (Application Performance Monitoring)**<br>Explore the APM console for detailed performance analysis and span visualization.<br><br><details><summary>What you'll see:</summary><ul><li>Service map showing agent and tool dependencies</li><li>Span waterfall visualization with timing breakdowns</li><li>Performance metrics and latency percentiles</li><li>Node health and error tracking</li></ul></details> | ▶️ **[Watch Video](https://github.com/user-attachments/assets/dfad7acc-0523-41b8-b961-f5480fc9e456)** |
| **Braintrust Dashboard**<br>Review how Braintrust captures and displays LLM-specific metrics and trace details.<br><br><details><summary>What you'll see:</summary><ul><li>Experiment list with run history and performance</li><li>Trace explorer with powerful filtering</li><li>LLM cost tracking and token usage breakdown</li><li>Span timeline visualization</li><li>Input/output analysis and quality metrics</li></ul></details> | ▶️ **[Watch Video](https://github.com/user-attachments/assets/d6ec96cb-17a7-41b8-a73d-d52a537842fa)** |

## Prerequisites

| Requirement | Description |
|-------------|-------------|
| Python 3.11+ | Python runtime for deployment scripts and agent code |
| pip | Python package installer for dependencies |
| Docker | Required for building agent containers. Install: https://docs.docker.com/get-docker/ |
| AWS Account | Active AWS account with Bedrock access enabled in your region |
| AWS CLI | Configured with credentials. Verify: `aws sts get-caller-identity` |
| IAM Permissions | Required permissions for AgentCore Runtime, CloudWatch, and X-Ray (see below) |
| Braintrust Account (Optional) | Optional free tier account for AI-focused observability. Sign up at https://www.braintrust.dev/signup. See [Braintrust Setup](docs/braintrust-setup.md) for detailed configuration. |
| Amazon Bedrock Access | Access to Claude 3.5 Haiku model in your region |

### Required IAM Permissions

The deployment process uses AWS CodeBuild to build Docker containers and deploy to AgentCore Runtime. Your IAM user or role needs comprehensive permissions.

#### Quick Setup: Attach Policy

A complete IAM policy is provided in [`docs/iam-policy-deployment.json`](docs/iam-policy-deployment.json).

**To attach the policy:**

```bash
# Using AWS CLI
aws iam put-user-policy \
  --user-name YOUR_IAM_USER \
  --policy-name BedrockAgentCoreDeployment \
  --policy-document file://docs/iam-policy-deployment.json

# Or for an IAM role
aws iam put-role-policy \
  --role-name YOUR_ROLE_NAME \
  --policy-name BedrockAgentCoreDeployment \
  --policy-document file://docs/iam-policy-deployment.json
```

#### Required Permission Categories

1. **CodeBuild** (for building Docker containers):
   - `codebuild:CreateProject`, `codebuild:UpdateProject`, `codebuild:StartBuild`
   - `codebuild:BatchGetBuilds`, `codebuild:BatchGetProjects`

2. **ECR** (for storing container images):
   - `ecr:CreateRepository`, `ecr:GetAuthorizationToken`
   - `ecr:PutImage`, `ecr:BatchCheckLayerAvailability`

3. **S3** (for CodeBuild source storage):
   - `s3:CreateBucket`, `s3:PutObject`, `s3:GetObject`

4. **IAM** (for creating execution roles):
   - `iam:CreateRole`, `iam:AttachRolePolicy`, `iam:PassRole`

5. **Bedrock AgentCore** (for agent deployment):
   - `bedrock-agentcore:*`

6. **Bedrock** (for model invocation):
   - `bedrock:InvokeModel`

7. **CloudWatch** (for observability):
   - `cloudwatch:PutMetricData`, `xray:PutTraceSegments`
   - `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`

See [`docs/iam-policy-deployment.json`](docs/iam-policy-deployment.json) for the complete policy.

## Environment Configuration

This tutorial supports optional configuration via a `.env` file for easier credential management.

### Setup .env File

A template is provided in `.env.example` (committed to the repository):

```bash
# Copy the example template
cp .env.example .env

# Edit .env with your values (file is in .gitignore, never committed)
```

**Configuration variables in .env:**

| Variable | Required | Purpose |
|----------|----------|---------|
| `AWS_REGION` | No | AWS region for deployment (default: `us-east-1`) |
| `BRAINTRUST_API_KEY` | Conditional | Braintrust API key for dual observability (optional) |
| `BRAINTRUST_PROJECT_ID` | Conditional | Braintrust project ID for dual observability (optional) |
| `AGENTCORE_AGENT_ID` | No | Agent ID (auto-saved to `.deployment_metadata.json` after deployment) |

**Important Notes:**
- The `.env` file is in `.gitignore` and will never be committed to the repository
- `.env.example` is committed as a template for reference
- Braintrust credentials are optional - omit them to use CloudWatch observability only
- For security, never commit actual credentials to the repository

## Quickstart

Get the agent running in 3 steps:

```bash
# 1. Install dependencies
uv sync

# 2. Deploy agent (with optional Braintrust observability)
# Option A: Use .env file (recommended for repeated deployments)
cp .env.example .env
# Edit .env - add your Braintrust credentials:
#   BRAINTRUST_API_KEY=your-api-key
#   BRAINTRUST_PROJECT_ID=your-project-id
# Agent will automatically export OTEL traces to both CloudWatch and Braintrust
scripts/deploy_agent.sh

# Option B: CloudWatch observability only (default, no Braintrust)
scripts/deploy_agent.sh --region us-east-1

# Option C: Add Braintrust credentials to .env and override region via command-line
# First, edit .env with your Braintrust credentials, then:
scripts/deploy_agent.sh --region us-west-2  # Will use credentials from .env

# Option D: Override both .env and command-line arguments
# Add exact parameter names to .env first:
#   BRAINTRUST_API_KEY=sk-your-actual-key
#   BRAINTRUST_PROJECT_ID=your-actual-project-id
# Then deploy with command-line overrides:
scripts/deploy_agent.sh \
    --region us-east-1 \
    --braintrust-api-key sk-your-override-key \
    --braintrust-project-id your-override-project-id
# Agent will export OTEL metrics and traces to Braintrust

# Option E: Call deploy_agent.py directly (advanced)
# Both deploy_agent.sh and deploy_agent.py support the same arguments:
uv run python scripts/deploy_agent.py \
    --region us-east-1 \
    --braintrust-api-key sk-your-api-key \
    --braintrust-project-id your-project-id

# 3. Test the agent
scripts/tests/test_agent.sh --test calculator
scripts/tests/test_agent.sh --test weather
scripts/tests/test_agent.sh --prompt "What time is it in Tokyo?"

# 4. Enable Tracing in CloudWatch Console (IMPORTANT)
# ⚠️ You MUST enable tracing to see traces from your agent
# Navigate to AWS CloudWatch Console:
#   1. Go to Agent Runtime
#   2. Select your agent from the list
#   3. Scroll all the way down to "Tracing" section
#   4. Click "Edit"
#   5. Click "Enable Tracing"
#   6. Press "Save" button
# If you skip this step, you will NOT see traces in CloudWatch!

# 5. Check CloudWatch logs to see traces
# View logs from the last 30 minutes
scripts/check_logs.sh --time 30m

# View only errors
scripts/check_logs.sh --errors

# Follow logs in real-time (useful while running tests)
scripts/check_logs.sh --follow

# View logs from the last hour
scripts/check_logs.sh --time 1h
```

**Available test commands:**
```bash
# Predefined tests
scripts/tests/test_agent.sh --test weather      # Test weather tool
scripts/tests/test_agent.sh --test time         # Test time tool
scripts/tests/test_agent.sh --test calculator   # Test calculator tool
scripts/tests/test_agent.sh --test combined     # Test multiple tools

# Custom prompts
scripts/tests/test_agent.sh --prompt "Your custom question here"

# Interactive mode
scripts/tests/test_agent.sh --interactive

# Show full response with traces
scripts/tests/test_agent.sh --test combined --full
```

**Load Testing:**
```bash
# Run quick load test (5 min, 2 req/min) - generates observability data
scripts/tests/run_load_test.sh quick

# Run standard test (15 min, 4 req/min)
scripts/tests/run_load_test.sh standard

# Run extended test (30 min, 5 req/min) - great for demos
scripts/tests/run_load_test.sh extended

# Focus on multi-tool queries
scripts/tests/run_load_test.sh multi-tool

# Include error scenarios (30% errors)
scripts/tests/run_load_test.sh errors

# Custom configuration
scripts/tests/run_load_test.sh --duration 20 --rate 5 --multi-tool 50
```

**Cleanup:**
```bash
# Delete agent and all resources
scripts/cleanup.sh

# Or delete without prompts
scripts/cleanup.sh --force

# Keep CloudWatch logs
scripts/cleanup.sh --keep-logs
```

For detailed configuration and setup instructions, see:
- **[Braintrust Setup](docs/braintrust-setup.md)** - Braintrust account creation, API key management, and dashboard setup
- **[System Design](docs/design.md)** - Complete architecture and OTEL trace flow details

## ⚠️ IMPORTANT: Enable Tracing After Deployment

**You MUST enable tracing in CloudWatch Console to see traces from your agent.**

After deploying your agent with `scripts/deploy_agent.sh`, follow these steps:

1. Open AWS CloudWatch Console: https://console.aws.amazon.com/cloudwatch
2. Navigate to **Agent Runtime** (left sidebar)
3. **Select your agent** from the list (name will be `weather_time_observability_agent-XXXXX`)
4. **Scroll all the way down** to the **Tracing** section
5. Click the **Edit** button
6. Check the box to **Enable Tracing**
7. Press the **Save** button

**⚠️ If you skip this step, you WILL NOT see any traces in CloudWatch!**

Once tracing is enabled, you can:
- View full distributed traces in CloudWatch X-Ray
- See all spans (LLM calls, tool invocations, agent reasoning)
- Correlate logs with traces using trace IDs
- Export the same traces to Braintrust (if configured)

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

View CloudWatch logs and X-Ray traces using the check_logs.sh script and AWS Console:

**Using check_logs.sh Script (Recommended for Quick Review):**
```bash
# View agent execution logs from the last 30 minutes
scripts/check_logs.sh --time 30m

# Follow logs in real-time while running tests
scripts/check_logs.sh --follow

# View only error messages
scripts/check_logs.sh --errors

# View logs from the last hour
scripts/check_logs.sh --time 1h
```

**Using CloudWatch X-Ray Console (Detailed Visualization):**

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
# Run cleanup script
scripts/cleanup.sh

# Or with force flag to skip confirmations
scripts/cleanup.sh --force
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
rm -f scripts/.deployment_metadata.json
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

## Next Steps

After completing this tutorial, consider:

1. Customize the built-in tools (weather, time, calculator) for your use case
2. Configure CloudWatch Alarms for error rate monitoring
3. Set up Braintrust evaluations for agent quality monitoring
4. Integrate observability into your production applications
5. Explore advanced OTEL features (custom spans, events, metrics)
6. Compare observability data across multiple platforms
7. Build custom dashboards tailored to your use case

## Disclaimer

The examples provided in this repository are for experimental and educational purposes only. They demonstrate concepts and techniques but are not intended for direct use in production environments without proper security hardening and testing. Make sure to have Amazon Bedrock Guardrails in place to protect against prompt injection and other security risks.
