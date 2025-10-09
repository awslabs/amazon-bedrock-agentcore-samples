# IAM Roles Setup for Bedrock AgentCore

This directory contains scripts to set up the necessary IAM roles for AWS Bedrock AgentCore applications with the correct permissions.

## Quick Setup

For a quick and easy setup, use the shell script:

```bash
./setup_role.sh
```

This script will:
1. Check for AWS credentials
2. Prompt for required information with sensible defaults
3. Create the IAM role with all necessary permissions
4. Display the role ARN for use in your configuration

## Manual Setup

If you prefer a more customized setup, you can use the Python modules:

1. Configure your settings by creating/editing `iam_config.ini`:
   ```bash
   python3 config.py
   ```

2. Run the setup interactively:
   ```bash
   python3 -c "from collect_info import run_interactive_setup; run_interactive_setup()"
   ```

## Required Permissions

The IAM role includes permissions for:
- **ECR (Elastic Container Registry)**: Access to pull Docker images
  - `ecr:GetAuthorizationToken` - Get authentication token
  - `ecr:BatchGetImage` - Pull container images
  - `ecr:GetDownloadUrlForLayer` - Download image layers
  - Resource: `arn:aws:ecr:*:ACCOUNT_ID:repository/bedrock-agentcore-*` (supports all agent repositories)
- **CloudWatch Logs**: Write application logs
- **X-Ray**: Distributed tracing
- **CloudWatch Metrics**: Publish custom metrics
- **Bedrock AgentCore**: Access tokens and workload identities
- **Bedrock Models**: Invoke foundation models
- **AgentCore Memory**: Store and retrieve conversation history
  - `bedrock-agentcore:CreateMemory` - Create memory resources
  - `bedrock-agentcore:GetMemory` - Retrieve memory resources
  - `bedrock-agentcore:CreateEvent` - Save conversation events
  - `bedrock-agentcore:RetrieveMemories` - Query stored memories
  - Resource: `arn:aws:bedrock-agentcore:*:ACCOUNT_ID:memory/*`

These permissions follow AWS best practices with least-privilege principle.

**Note**: The ECR permissions use a wildcard (`bedrock-agentcore-*`) to support any agent name you deploy. This is required for the agent runtime to pull your Docker images from ECR.

## Prerequisites

- AWS CLI installed and configured with appropriate permissions
- AWS account with permissions to create IAM roles and policies

## Files

- `setup_role.sh` - Quick setup shell script
- `config.py` - Configuration management
- `policy_templates.py` - IAM policy templates
- `collect_info.py` - Interactive configuration collection
- `trust-policy.json` - Trust relationship policy template

## Troubleshooting

If you encounter any issues, check:

- AWS credentials are properly configured (`aws configure`)
- You have sufficient permissions to create IAM roles
- AWS CLI is installed and in your PATH

## Security Note

The created IAM roles follow security best practices:
- Strict trust policy with conditions
- Least privilege principle for permissions
- Resource-based limitations where possible