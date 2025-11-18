# AgentCore Observability Scripts

Deployment and setup scripts for the Simple Dual Observability Tutorial.

## Overview

These scripts automate the complete setup of Amazon Bedrock AgentCore observability with Braintrust support.

**Note:** All commands in this documentation assume you are running from the tutorial root directory (`simple-dual-observability`), not from within the `scripts/` folder. Use `scripts/<script-name>.sh` to invoke the scripts.

## Scripts

### check_prerequisites.sh

Verify all prerequisites are met before running setup.

```bash
# Run prerequisite checks
scripts/check_prerequisites.sh

# Run with verbose output
scripts/check_prerequisites.sh --verbose
```

**What it does:**
1. Checks AWS CLI installation and configuration
2. Verifies Python 3.11+ is installed
3. Checks required Python packages (boto3)
4. Validates AWS credentials and permissions
5. Tests service availability (AgentCore, CloudWatch, X-Ray)
6. Provides actionable fixes for any issues

Run this first before any other scripts.

### setup_all.sh

Complete end-to-end setup orchestration.

```bash
# Setup with default settings
scripts/setup_all.sh

# Setup with Braintrust integration
scripts/setup_all.sh --api-key bt-xxxxx --project-id your-project-id

# Setup in specific region
scripts/setup_all.sh --region us-west-2
```

**What it does:**
1. Deploys agent to AgentCore Runtime
2. Optionally configures Braintrust integration

### deploy_agent.sh

Deploy Strands agent to AgentCore Runtime.

```bash
# Deploy with defaults
scripts/deploy_agent.sh

# Deploy with custom region and model
scripts/deploy_agent.sh --region us-west-2 --model anthropic.claude-3-haiku-20240307-v1:0

# Deploy with Braintrust integration
export BRAINTRUST_API_KEY=your_api_key_here
scripts/deploy_agent.sh
```

**What it does:**
1. Creates agent configuration with tools (weather, time, calculator)
2. Deploys agent to AgentCore Runtime
3. Configures OTEL environment variables
4. Saves agent ID for use in demo

**Environment Variables:**
- `AWS_REGION` - AWS region for deployment
- `AGENT_NAME` - Name for the agent
- `MODEL_ID` - Bedrock model identifier
- `BRAINTRUST_API_KEY` - Braintrust API key (optional)
- `SERVICE_NAME` - Service name for OTEL traces

### cleanup.sh

Remove all resources created by the tutorial.

```bash
# Interactive cleanup
scripts/cleanup.sh

# Force cleanup without prompts
scripts/cleanup.sh --force

# Cleanup but keep logs
scripts/cleanup.sh --keep-logs
```

**What it does:**
1. Deletes deployed agent from AgentCore Runtime
2. Cleans up local configuration files

**Environment Variables:**
- `AWS_REGION` - AWS region for resources

## Quick Start

### Step 0: Check Prerequisites

```bash
scripts/check_prerequisites.sh
```

Fix any issues reported before proceeding.

### Basic Setup

```bash
scripts/setup_all.sh

# Run observability demo (automatically reads agent ID from metadata)
python simple_observability.py --scenario all
```

### Setup with Braintrust

```bash
# With Braintrust API key from environment
export BRAINTRUST_API_KEY=your_api_key_here
export BRAINTRUST_PROJECT_ID=your_project_id
scripts/setup_all.sh

# Or pass as arguments
scripts/setup_all.sh --api-key your_api_key_here --project-id your_project_id

# Run observability demo
python simple_observability.py --scenario all
```

### Manual Step-by-Step

```bash
# 1. Deploy agent
scripts/deploy_agent.sh

# 2. Run demo (automatically reads agent ID from .deployment_metadata.json)
python simple_observability.py --scenario all
```

## Generated Files

After running the scripts, the following files are created:

- `.agent_id` - Deployed agent ID
- `.env` - Environment configuration with API keys and region
- `braintrust-usage.md` - Braintrust usage guide (if configured)
- `.env.backup` - Backup of .env (created during cleanup)

## Prerequisites

### Required

- AWS CLI configured with credentials
- Python 3.11+
- boto3 installed
- Amazon Bedrock AgentCore access in your region

### For Braintrust Integration

- Braintrust account (free signup at https://www.braintrust.dev)
- Braintrust API key

## Common Operations

### View Agent Configuration

```bash
# Get agent ID
AGENT_ID=$(cat .agent_id)

# Describe agent
aws bedrock-agentcore-runtime describe-agent \
    --agent-id $AGENT_ID \
    --region us-east-1
```

### View Traces

```bash
# Braintrust (if configured)
echo "https://www.braintrust.dev/app"
```

### Update Agent Configuration

```bash
# Cleanup old agent
scripts/cleanup.sh

# Deploy with new configuration
scripts/deploy_agent.sh --model anthropic.claude-3-opus-20240229-v1:0
```

## Troubleshooting

### Agent Deployment Fails

Check:
1. AWS credentials are configured: `aws sts get-caller-identity`
2. Region supports AgentCore Runtime: `aws bedrock-agentcore-runtime help`
3. You have necessary IAM permissions

### No Traces in Braintrust

Check:
1. API key is correctly configured
2. Project ID is valid
3. Agent has been invoked at least once
4. Check Braintrust dashboard after a few seconds

## Support

For issues specific to:
- AgentCore: AWS Support or Bedrock documentation
- Braintrust: support@braintrust.dev

## Additional Resources

- AgentCore Documentation: [Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock/)
- Braintrust: [Braintrust Documentation](https://www.braintrust.dev/docs)
- OpenTelemetry: [OTEL Documentation](https://opentelemetry.io/docs/)
