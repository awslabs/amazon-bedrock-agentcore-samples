# AgentCore Observability Scripts

Deployment and setup scripts for the Simple Dual Observability Tutorial.

## Overview

These scripts automate the complete setup of Amazon Bedrock AgentCore observability with dual platform support (CloudWatch and Braintrust).

**Note:** All commands in this documentation assume you are running from the tutorial root directory (`07-simple-dual-observability`), not from within the `scripts/` folder. Use `scripts/<script-name>.sh` to invoke the scripts.

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
# Setup with CloudWatch only
scripts/setup_all.sh

# Setup with CloudWatch and Braintrust (interactive)
scripts/setup_all.sh --braintrust

# Setup with existing Braintrust API key
scripts/setup_all.sh --api-key bt-xxxxx

# Setup in specific region
scripts/setup_all.sh --region us-west-2
```

**What it does:**
1. Deploys agent to AgentCore Runtime
2. Sets up CloudWatch dashboard and X-Ray
3. Optionally configures Braintrust integration

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

### setup_cloudwatch.sh

Configure CloudWatch Transaction Search and dashboard.

```bash
# Setup with defaults
scripts/setup_cloudwatch.sh

# Setup with custom region
scripts/setup_cloudwatch.sh --region us-west-2

# Setup with custom dashboard name
scripts/setup_cloudwatch.sh --dashboard MyAgentCoreDashboard
```

**What it does:**
1. Creates CloudWatch log groups
2. Sets log retention policies
3. Enables X-Ray tracing
4. Creates CloudWatch dashboard with:
   - Agent response latency (P50, P90, P99)
   - Token consumption
   - Error counts
   - Recent trace events
   - Bedrock invocations
   - Latency by operation
5. Generates IAM policy template
6. Outputs dashboard URLs

**Environment Variables:**
- `AWS_REGION` - AWS region for resources
- `DASHBOARD_NAME` - CloudWatch dashboard name
- `LOG_GROUP_NAME` - CloudWatch log group name
- `NAMESPACE` - CloudWatch metrics namespace

### setup_braintrust.sh

Configure Braintrust integration for AI-focused observability.

```bash
# Interactive setup
scripts/setup_braintrust.sh

# Setup with existing API key
scripts/setup_braintrust.sh --api-key bt-xxxxx

# Test existing configuration
scripts/setup_braintrust.sh --test
```

**What it does:**
1. Guides through Braintrust account creation
2. Helps generate API key
3. Configures OTEL integration
4. Tests connection to Braintrust API
5. Creates dual-export OTEL config
6. Generates usage documentation

**Environment Variables:**
- `BRAINTRUST_API_KEY` - Braintrust API key
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
2. Removes CloudWatch dashboard
3. Deletes CloudWatch log groups (optional)
4. Cleans up local configuration files

**Environment Variables:**
- `AWS_REGION` - AWS region for resources
- `DASHBOARD_NAME` - CloudWatch dashboard name
- `LOG_GROUP_NAME` - CloudWatch log group name

## Quick Start

### Step 0: Check Prerequisites

```bash
scripts/check_prerequisites.sh
```

Fix any issues reported before proceeding.

### Minimal Setup (CloudWatch only)

```bash
scripts/setup_all.sh

# Run observability demo (automatically reads agent ID from metadata)
python simple_observability.py --scenario all
```

### Full Setup (CloudWatch + Braintrust)

```bash
scripts/setup_all.sh --braintrust

# Run observability demo with Braintrust
export BRAINTRUST_API_KEY=your_api_key_here
python simple_observability.py --scenario all
```

### Manual Step-by-Step

```bash
# 1. Deploy agent
scripts/deploy_agent.sh

# 2. Setup CloudWatch
scripts/setup_cloudwatch.sh

# 3. (Optional) Setup Braintrust
scripts/setup_braintrust.sh

# 4. Run demo (automatically reads agent ID from .deployment_metadata.json)
python simple_observability.py --scenario all
```

## Generated Files

After running the scripts, the following files are created:

- `.agent_id` - Deployed agent ID
- `.env` - Environment configuration with API keys and region
- `cloudwatch-urls.txt` - Direct links to CloudWatch resources
- `xray-permissions.json` - IAM policy template for X-Ray
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
# Load environment
source .env

# CloudWatch X-Ray
echo "https://console.aws.amazon.com/cloudwatch/home?region=$AWS_REGION#xray:traces"

# Braintrust
echo "https://www.braintrust.dev/app"
```

### Update Agent Configuration

```bash
# Cleanup old agent
scripts/cleanup.sh

# Deploy with new configuration
scripts/deploy_agent.sh --model anthropic.claude-3-opus-20240229-v1:0
```

### Test Braintrust Connection

```bash
export BRAINTRUST_API_KEY=your_api_key_here
scripts/setup_braintrust.sh --test
```

## Troubleshooting

### Agent Deployment Fails

Check:
1. AWS credentials are configured: `aws sts get-caller-identity`
2. Region supports AgentCore Runtime: `aws bedrock-agentcore-runtime help`
3. You have necessary IAM permissions

### No Traces in CloudWatch

Check:
1. Log group exists: `aws logs describe-log-groups --log-group-name-prefix /aws/agentcore`
2. X-Ray is enabled: `aws xray get-sampling-rules`
3. IAM role has X-Ray permissions (see `xray-permissions.json`)

### No Traces in Braintrust

Check:
1. API key is valid: `scripts/setup_braintrust.sh --test`
2. OTEL config has Braintrust exporter enabled
3. Network connectivity to api.braintrust.dev

### Dashboard Shows No Data

Check:
1. Run the demo to generate traces
2. Wait 2-5 minutes for metric aggregation
3. Verify metric namespace matches: `AgentCore/Observability`

## Support

For issues specific to:
- AgentCore: AWS Support or Bedrock documentation
- CloudWatch/X-Ray: AWS Support
- Braintrust: support@braintrust.dev

## Additional Resources

- AgentCore Documentation: [AWS Bedrock AgentCore](https://docs.aws.amazon.com/bedrock/)
- CloudWatch X-Ray: [AWS X-Ray Documentation](https://docs.aws.amazon.com/xray/)
- Braintrust: [Braintrust Documentation](https://www.braintrust.dev/docs)
- OpenTelemetry: [OTEL Documentation](https://opentelemetry.io/docs/)
