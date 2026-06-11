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
- ECR (container registry access)
- CloudWatch Logs
- X-Ray tracing
- CloudWatch metrics
- Bedrock AgentCore access tokens
- Bedrock model invocation

These permissions follow AWS best practices with least-privilege principle.

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