# Bedrock AgentCore Cognito Authentication Setup

This directory contains scripts for setting up and managing AWS Cognito authentication for your Bedrock AgentCore application.

## Quick Setup

For a quick and easy setup, use the setup script:

```bash
./setup_cognito.sh
```

This script will:
1. Check for AWS credentials and required tools (AWS CLI, jq)
2. Prompt for required information with sensible defaults:
   - AWS region
   - User Pool name
   - App Client name
   - Test user credentials
3. Create the Cognito User Pool and App Client
4. Create a test user with the specified credentials
5. Generate an access token for immediate use
6. Save all configuration to easily accessible files

## Configuration Files

After running the setup script, you'll have the following files:

- `cognito_config.json` - Contains all configuration details and access token
- `cognito_result.md` - A formatted summary of the setup for documentation

## Refreshing Access Tokens

Cognito access tokens expire after one hour by default. To refresh your token:

```bash
./refresh_token.sh
```

This will:
1. Use the stored credentials in the config file
2. Request a new access token from Cognito
3. Update the configuration file automatically

## Required Permissions

To run these scripts, your AWS user must have the following permissions:

- Amazon Cognito Identity Provider full access (`cognito-idp:*`) 
- Or at minimum, permissions to:
  - CreateUserPool
  - CreateUserPoolClient
  - AdminCreateUser
  - AdminSetUserPassword
  - InitiateAuth

## Prerequisites

- AWS CLI installed and configured with appropriate permissions
- jq (JSON processor) installed for parsing outputs

## Security Notes

- The created user pool follows security best practices
- Password policies can be adjusted in the setup script
- For production use, consider additional security measures:
  - Multi-factor authentication
  - Custom password policies
  - Token revocation strategies