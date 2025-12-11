# Simple Dual Platform Observability Tutorial

## Overview

This tutorial demonstrates two observability approaches for Amazon Bedrock AgentCore agents:

1. **CloudWatch Observability (Default & Always Active)**: AgentCore Runtime automatically provides vended traces to CloudWatch Logs with zero configuration
2. **Braintrust Observability (Optional)**: Add AI-focused observability by exporting OpenTelemetry traces from the agent to Braintrust platform

The tutorial shows how AgentCore Runtime provides automatic observability via CloudWatch, with the optional ability to add AI-focused monitoring through Braintrust by exporting OpenTelemetry traces from your Strands agent. Note: CloudWatch traces are provided by AgentCore Runtime infrastructure, while Braintrust receives OTEL traces directly from your agent code.

### Use case details
| Information         | Details                                                                                                                             |
|---------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| Use case type       | observability, monitoring                                                                                                           |
| Agent type          | Single agent with tools                                                                                                             |
| Use case components | AgentCore Runtime, Strands Agent, built-in tools, dual-platform observability (CloudWatch + Braintrust)                          |
| Use case vertical   | DevOps, Platform Engineering, AI Operations                                                                                        |
| Example complexity  | Intermediate                                                                                                                        |
| SDK used            | Amazon Bedrock AgentCore Runtime, boto3, OpenTelemetry, Strands                                                                   |

## Assets

| Asset | Description |
|-------|-------------|
| CloudWatch Dashboard | Pre-configured dashboard showing agent metrics, latency, and error rates |
| Braintrust Project | AI-focused observability with LLM cost tracking and quality metrics |
| Sample Agent | Weather, time, and calculator tools demonstrating tool execution tracing |

### Use case Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  OBSERVABILITY ARCHITECTURE                                         │
│                                                                     │
│  Your Laptop                                                        │
│    ↓ (runs simple_observability.py or test_agent.sh)              │
│  Python CLI Script (boto3 client)                                  │
│    ↓ (API call: invoke_agent)                                      │
│  AgentCore Runtime (Managed Service)                               │
│    ├─ Automatic CloudWatch Instrumentation (AgentCore managed)    │
│    │  └─ Vended traces to CloudWatch Logs                         │
│    ├─ Strands Agent (deployed to Runtime)                         │
│    │  ├─ Weather Tool (built-in)                                  │
│    │  ├─ Time Tool (built-in)                                     │
│    │  └─ Calculator Tool (built-in)                               │
│    │  └─ OTEL Exporter (optional, if BRAINTRUST_API_KEY is set)  │
│    │                                                               │
│  ┌──────────────────────────┬────────────────────────────────────┐
│  │ CloudWatch Logs          │ Braintrust (Optional)              │
│  │ (from AgentCore Runtime) │ (from Strands OTEL export)         │
│  │ Always enabled           │ Only if BRAINTRUST_API_KEY is set  │
│  └──────────────────────────┴────────────────────────────────────┘
│                                                                     │
│  Key: CloudWatch = automatic infrastructure-level observability    │
│       Braintrust = optional agent-level OTEL export (if enabled)   │
│       Different trace sources, complementary platforms             │
└─────────────────────────────────────────────────────────────────────┘
```

### Use case key Features

- **Automatic CloudWatch Observability**: AgentCore Runtime automatically provides vended traces to CloudWatch Logs with zero code changes
- **Optional Braintrust Export**: Strands agent can optionally export OpenTelemetry traces directly to Braintrust platform for AI-focused monitoring
- **Dual-Platform Capability**: View the same agent execution in CloudWatch (AWS-native) and optionally in Braintrust (AI-focused) using different trace sources
- **Fully Managed Runtime**: AgentCore Runtime handles all infrastructure management and automatic CloudWatch instrumentation
- **Built-in Tools**: Strands agent with weather, time, and calculator tools for demonstration
- **Comprehensive Tracing**: Captures agent invocation, model calls, tool selection, and execution spans in both platforms
- **Platform Comparison**: Demonstrates AWS-native vs AI-focused observability strengths and trade-offs

## Detailed Documentation

For comprehensive information about this observability tutorial, please refer to the following detailed documentation:

### Observability Guides
- **[Observability Options](docs/observability-options.md)** - Comparison of three deployment approaches, actual CloudWatch logs, and what each platform captures
- **[Design & Architecture](docs/design.md)** - System architecture, component interactions, and OTEL flow diagrams

### Setup and Configuration
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
| IAM Permissions | Required permissions for AgentCore Runtime and CloudWatch (see below) |
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
   - `cloudwatch:PutMetricData`, `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`

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
| `AWS_PROFILE` | No | AWS credential profile (default: `default`). Use if you have multiple profiles configured locally |
| `BRAINTRUST_API_KEY` | Conditional | Braintrust API key for dual observability (optional) |
| `BRAINTRUST_PROJECT_ID` | Conditional | Braintrust project ID for dual observability (optional) |
| `AGENTCORE_AGENT_ID` | No | Agent ID (auto-saved to `.deployment_metadata.json` after deployment) |

**Important Notes:**
- The `.env` file is in `.gitignore` and will never be committed to the repository
- `.env.example` is committed as a template for reference
- Braintrust credentials are optional - omit them to use CloudWatch observability only
- For security, never commit actual credentials to the repository

### AWS Credential Configuration

If running from your local machine (not from an AWS compute instance like EC2), configure AWS credentials using one of these methods:

**Option 1: Using AWS CLI Configuration (Recommended)**

Configure credentials using AWS CLI with named profiles:

```bash
# Set up a new profile (interactive)
aws configure --profile dev-profile

# This will prompt for:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region
# - Default output format

# Then specify the profile in .env or when running commands
export AWS_PROFILE=dev-profile
scripts/deploy_agent.sh
```

**Option 2: Using Environment Variables**

Set credentials directly as environment variables:

```bash
export AWS_ACCESS_KEY_ID=your-access-key
export AWS_SECRET_ACCESS_KEY=your-secret-key
export AWS_REGION=us-east-1
scripts/deploy_agent.sh
```

**Option 3: Using IAM Role (For EC2 instances)**

If running on an EC2 instance or other AWS compute service, an IAM role is automatically available. No manual credential configuration is needed:

```bash
# Simply run without setting credentials
scripts/deploy_agent.sh  # Uses IAM role automatically
```

**Option 4: Use .env File with Profile**

Store your profile preference in `.env`:

```bash
# .env file
AWS_PROFILE=dev-profile
AWS_REGION=us-east-1
```

Then run without additional environment variables:

```bash
scripts/deploy_agent.sh  # Uses AWS_PROFILE from .env
```

**Verify Credentials Are Working:**

```bash
# Check which AWS account/user is configured
aws sts get-caller-identity

# Expected output:
# {
#     "UserId": "AIDAI...",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/your-username"
# }
```

For detailed AWS CLI credential configuration, see [AWS CLI Configuration Guide](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html).

### Automatic Deployment Metadata Loading

After deploying your agent with `scripts/deploy_agent.sh`, the script automatically saves deployment information (including agent ID and ARN) to `.deployment_metadata.json` in the `scripts/` directory.

**Key benefit**: You don't always need to manually set the `AGENTCORE_AGENT_ID` environment variable. When running the demo or test scripts, the code automatically reads the agent ID from `.deployment_metadata.json` if the environment variable is not set.

**Priority order** for agent ID resolution:
1. Command-line argument: `--agent-id <agent-id>`
2. Deployment metadata file: `scripts/.deployment_metadata.json` (if it exists)
3. Environment variable: `AGENTCORE_AGENT_ID` or `AGENTCORE_AGENT_ARN`

This means after your initial deployment, you can simply run:
```bash
# These commands will work without setting AGENTCORE_AGENT_ID
# because the agent ID is automatically loaded from .deployment_metadata.json
uv run python simple_observability.py --scenario all
scripts/tests/test_agent.sh --test weather
```

The metadata file contains:
- `agent_id`: The unique identifier for your agent
- `agent_arn`: The full Amazon Resource Name for your agent
- `deployment_timestamp`: When the agent was deployed
- Other deployment configuration

**Note**: If you delete your agent using `scripts/delete_agent.py`, the metadata file is also cleaned up, and you'll need to redeploy before running the demo scripts again.

## Quickstart

Get the agent running in 3 steps:

```bash
# 1. Install dependencies
uv sync

# 2. Deploy agent (with optional Braintrust observability)
# Option A: Use .env file (recommended for repeated deployments)
cp .env.example .env
# Edit .env - add your Braintrust credentials (optional):
#   BRAINTRUST_API_KEY=bt-xxxxxxxxxxxxxxxxxxxxx
# CloudWatch tracing is automatic. Braintrust is optional (only if BRAINTRUST_API_KEY is set)
scripts/deploy_agent.sh

# Option B: CloudWatch observability only (default, no Braintrust)
scripts/deploy_agent.sh --region us-east-1

# Option C: Add Braintrust credentials to .env and override region via command-line
# First, edit .env with your Braintrust credentials, then:
scripts/deploy_agent.sh --region us-west-2  # Will use credentials from .env

# Option D: Override both .env and command-line arguments
# Add exact parameter names to .env first:
#   BRAINTRUST_API_KEY=bt-xxxxxxxxxxxxxxxxxxxxx
# Then deploy with command-line overrides:
scripts/deploy_agent.sh \
    --region us-east-1 \
    --braintrust-api-key bt-xxxxxxxxxxxxxxxxxxxxx
# Agent will export OTEL traces to Braintrust (CloudWatch is automatic)

# Option E: Update existing agent (auto-update on conflict)
# Use this flag to update an already-deployed agent instead of creating a new one:
scripts/deploy_agent.sh --auto-update-on-conflict
# This is useful when redeploying after running delete_agent.py

# Option F: Call deploy_agent.py directly (advanced)
# Both deploy_agent.sh and deploy_agent.py support the same arguments:
uv run python scripts/deploy_agent.py \
    --region us-east-1 \
    --braintrust-api-key sk-user-xxxxxxxxxxxxxxxxxxxxx \
    --braintrust-project-id proj-xxxxxxxxxxxxxxxxxxxxx \
    --auto-update-on-conflict

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
# Using the shell script (simple):
# View logs from the last 30 minutes
scripts/check_logs.sh --time 30m

# View only errors
scripts/check_logs.sh --errors

# Follow logs in real-time (useful while running tests)
scripts/check_logs.sh --follow

# View logs from the last hour
scripts/check_logs.sh --time 1h

# Or using the Python script for more options (see CloudWatch Logs section below):
uv run python scripts/get_cw_logs.py --follow
```

## Deployment Scenarios

### Initial Deployment

For the first deployment, use any of the options in the Quickstart section:

```bash
scripts/deploy_agent.sh
```

This creates a new agent with a unique agent ID and saves deployment metadata to `.deployment_metadata.json`.

### Redeploying After Agent Deletion

If you've deleted an agent using `scripts/delete_agent.py` and want to redeploy:

```bash
# After running: uv run python scripts/delete_agent.py
# This deletes the agent and cleans up metadata files

# To redeploy the agent with auto-update on conflict:
scripts/deploy_agent.sh --auto-update-on-conflict
```

The `--auto-update-on-conflict` flag tells the deployment script to:
- Check if an agent with the same name already exists
- If it does, automatically update it instead of failing
- Recreate `.deployment_metadata.json` with the new agent ID

### Updating an Existing Agent

To update agent code without deleting and redeploying:

```bash
# Modify your agent code (e.g., agent/weather_time_agent.py)
# Then redeploy with auto-update:
scripts/deploy_agent.sh --auto-update-on-conflict
```

This is faster than the delete-and-redeploy workflow and preserves existing observability data.

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
- View CloudWatch Logs for the Agent
- See all spans (LLM calls, tool invocations, agent reasoning)
- Correlate logs with traces using trace IDs

## Running the tutorial

The demo script provides three scenarios demonstrating different observability features.

The agent ID is automatically loaded from `.deployment_metadata.json` (see [Automatic Deployment Metadata Loading](#automatic-deployment-metadata-loading) above), so you don't need to specify `--agent-id` unless you want to override it.

### Run All Scenarios (Recommended)

Run all three scenarios sequentially with automatic delays between each:

```bash
# From tutorial root directory
# The agent ID is automatically loaded from .deployment_metadata.json
uv run python simple_observability.py --scenario all

# Or explicitly provide the agent ID
uv run python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario all
```

### Run Individual Scenarios

**Scenario 1: Successful Multi-Tool Query**

Demonstrates successful agent execution with multiple tool calls:

```bash
# Automatically uses agent ID from .deployment_metadata.json
uv run python simple_observability.py --scenario success

# Or explicitly provide the agent ID
uv run python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario success
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
# Automatically uses agent ID from .deployment_metadata.json
uv run python simple_observability.py --scenario error

# Or explicitly provide the agent ID
uv run python simple_observability.py --agent-id $AGENTCORE_AGENT_ID --scenario error
```

Query: "Calculate the factorial of -5"

Expected behavior:
- Agent selects calculator tool
- Tool returns error (invalid input for factorial)
- Error status recorded in spans
- Graceful error handling visible in traces

### Additional Options

```bash
# Enable debug logging for detailed execution traces
# (agent ID automatically loaded from .deployment_metadata.json)
uv run python simple_observability.py --scenario all --debug

# Specify different AWS region
uv run python simple_observability.py --region us-west-2 --scenario success

# Override metadata with explicit agent ID
uv run python simple_observability.py --agent-id <your-agent-id> --scenario success

# Using environment variables (as fallback if metadata file not found)
export AGENTCORE_AGENT_ID=abc123xyz
uv run python simple_observability.py

# Minimal command (uses defaults from .deployment_metadata.json)
uv run python simple_observability.py
```

## Expected Results

### CloudWatch Logs

View CloudWatch logs using the check_logs.sh script and AWS Console:

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

**What You'll See:**
- Agent execution timestamps
- Tool invocation logs
- Model calls and responses
- Execution status and completion messages
- Error messages and stack traces (Scenario 2)
- Performance metrics and latencies

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

**CloudWatch (Automatic, Infrastructure-Level Traces from AgentCore Runtime):**
- Native AWS integration with other services
- CloudWatch Alarms for automated alerting
- VPC Flow Logs correlation
- Longer retention options (up to 10 years)
- Integration with AWS Systems Manager and AWS Config
- Receives vended traces from AgentCore Runtime

**Braintrust (Optional, Agent-Level OTEL Traces from Strands Agent):**
- AI-focused metrics (quality scores, hallucination detection)
- LLM cost tracking across providers
- Prompt version comparison and A/B testing
- Evaluation frameworks for quality assurance
- Specialized AI/ML visualizations and analytics
- Requires `BRAINTRUST_API_KEY` environment variable

**Both Platforms Provide:**
- Real-time trace ingestion
- Query by trace ID or session ID
- Span-level detail with attributes
- Support for distributed tracing
- **Note**: Different trace sources (vended traces vs OTEL format), not identical

## Cleanup

To avoid unnecessary AWS charges, delete all created resources:

```bash
# Run cleanup script
scripts/cleanup.sh

# Or with force flag to skip confirmations
scripts/cleanup.sh --force
```

## Additional Resources

### Documentation
- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agentcore.html)
- [CloudWatch Logs Documentation](https://docs.aws.amazon.com/AmazonCloudWatch/latest/logs/)
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
