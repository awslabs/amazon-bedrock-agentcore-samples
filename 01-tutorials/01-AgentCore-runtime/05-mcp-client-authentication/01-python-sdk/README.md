# MCP Client Authentication with Python SDK

## Overview

This tutorial demonstrates how to use standard MCP Python SDK to access MCP servers hosted on Amazon Bedrock AgentCore Runtime using different authentication methods. It provides standalone Python applications that work independently to connect to your AgentCore-hosted MCP servers.

## Authentication Methods

This tutorial includes two authentication approaches:

| Method | Authentication | Use Case | User Interaction | Setup Complexity |
|--------|---------------|----------|------------------|------------------|
| **OAuth 2.0** | Token-based | User applications, interactive flows | Required (except M2M) | Medium |
| **AWS SigV4** | IAM credentials | Service-to-service, automated systems | None | Simple |

### OAuth 2.0 Client (`mcp_oauth_client.py`)

Supports 4 different authentication modes:
- **Mode 1 (Manual)**: Interactive OAuth flow with browser redirect and step-by-step debugging
- **Mode 2 (Quick)**: Direct authentication using test credentials (AWS Cognito only)
- **Mode 3 (M2M)**: Machine-to-machine client credentials flow for service-to-service authentication
- **Mode 4 (Native SDK)**: Uses official MCP SDK OAuth with automatic token management

### AWS SigV4 Client (`mcp_sigv4_client.py`)

Uses AWS IAM credentials for authentication:
- Support for AWS profiles, roles, and access keys
- No user interaction required
- Direct service-to-service authentication
- Custom region configuration

## Prerequisites

### For OAuth Authentication

1. **AWS Cognito User Pool** (or other OAuth 2.0 provider)
2. **App Client** configured with proper OAuth flows
3. **Test user account** (for interactive modes)

### For SigV4 Authentication

1. **AWS IAM credentials** configured
2. **Proper IAM permissions** for AgentCore runtime access
3. **AgentCore runtime ARN**

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy the example configuration
cp .env.example .env.local

# Edit .env.local with your actual values
# At minimum, set:
# - OAUTH_DISCOVERY_URL
# - OAUTH_CLIENT_ID  
# - AGENTCORE_RUNTIME_ARN
```

### 3. Run OAuth Client

```bash
# Load environment variables
source .env.local

# Run the OAuth client
python mcp_oauth_client.py
```

### 4. Run SigV4 Client

```bash
# Ensure AWS credentials are configured
aws configure  # or use AWS_PROFILE, IAM roles, etc.

# Run with AgentCore ARN
python mcp_sigv4_client.py --agent-arn arn:aws:bedrock-agentcore:us-west-2:YOUR_ACCOUNT:runtime/YOUR_AGENT
```

## Detailed Setup Instructions

### OAuth 2.0 Setup with AWS Cognito

#### 1. Create User Pool App Client

Your AWS Cognito User Pool App Client must be configured with:

**Required Settings:**
- **Callback URLs**: `http://localhost:3000`
- **Sign-out URLs**: `http://localhost:3000`
- **OAuth 2.0 grant types**: 
  - ✅ Authorization code grant (for interactive modes)
  - ✅ Client credentials (for M2M mode)
- **OAuth 2.0 scopes**:
  - ✅ `openid`
  - ✅ `email` 
  - ✅ `aws.cognito.signin.user.admin`

#### 2. Configure Using AWS CLI

```bash
# Enable required OAuth flows
aws cognito-idp update-user-pool-client \\
  --user-pool-id us-west-2_YourPoolId \\
  --client-id your_client_id \\
  --allowed-o-auth-flows "code" "client_credentials" \\
  --allowed-o-auth-scopes "openid" "email" "aws.cognito.signin.user.admin" \\
  --callback-ur-ls "http://localhost:3000" \\
  --logout-ur-ls "http://localhost:3000" \\
  --allowed-o-auth-flows-user-pool-client

# Generate client secret (required for M2M mode)
aws cognito-idp update-user-pool-client \\
  --user-pool-id us-west-2_YourPoolId \\
  --client-id your_client_id \\
  --generate-secret
```

#### 3. Environment Configuration

Update your `.env.local` file:

```bash
# Required for all OAuth modes
OAUTH_DISCOVERY_URL=https://cognito-idp.us-west-2.amazonaws.com/us-west-2_YourPoolId/.well-known/openid-configuration
OAUTH_CLIENT_ID=your_cognito_client_id
AGENTCORE_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/your-runtime-id

# Optional: for Quick mode (Mode 2)
OAUTH_TEST_USERNAME=test@example.com
OAUTH_TEST_PASSWORD=your_test_password

# Optional: for M2M mode (Mode 3)
OAUTH_CLIENT_SECRET=your_client_secret
```

### SigV4 Setup with AWS IAM

#### 1. Configure AWS Credentials

```bash
# Option 1: AWS CLI configuration
aws configure

# Option 2: Use AWS Profile
export AWS_PROFILE=your-profile-name
```

#### 2. IAM Permissions

Ensure your IAM user/role has permissions to invoke AgentCore runtime.

#### 3. Get Your AgentCore Runtime ARN

```bash
# List available runtimes
aws bedrock-agentcore-control list-agent-runtimes

# Your ARN format will be:
# arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/RUNTIME_ID
```

## Usage Examples

### OAuth Authentication Modes

#### Mode 1: Manual Interactive Flow
```bash
python mcp_oauth_client.py
# Select Mode 1
# Follow browser prompts for authorization
```

#### Mode 2: Quick Authentication (Cognito Only)
```bash
# Set test credentials in .env.local
export OAUTH_TEST_USERNAME=test@example.com
export OAUTH_TEST_PASSWORD=your_password

python mcp_oauth_client.py
# Select Mode 2
```

#### Mode 3: Machine-to-Machine
```bash
# Set client secret in .env.local
export OAUTH_CLIENT_SECRET=your_client_secret

python mcp_oauth_client.py
# Select Mode 3
```

#### Mode 4: Native SDK (Recommended)
```bash
python mcp_oauth_client.py
# Select Mode 4
# Auto-detects M2M vs Interactive based on client_secret presence
```

### SigV4 Authentication

```bash
# Basic usage
python mcp_sigv4_client.py --agent-arn arn:aws:bedrock-agentcore:us-west-2:123456789012:runtime/your-runtime

# With custom region
python mcp_sigv4_client.py -a arn:aws:bedrock-agentcore:us-east-1:123456789012:runtime/your-runtime --region us-east-1

# Show help
python mcp_sigv4_client.py --help
```

## What the Clients Do

Both clients demonstrate the MCP workflow:

1. **Authentication**: Establish secure connection to AgentCore
2. **Session Initialization**: Start MCP protocol session
3. **Tool Discovery**: List all available MCP tools
4. **Tool Invocation**: Call tools with parameters (if configured)
5. **Response Handling**: Process and display results

### Example Output

```
🔍 Discovering OAuth 2.0 endpoints...
✓ OAuth endpoints discovered successfully

🔐 Starting OAuth authentication (Mode 4 - Native SDK)...
✓ Authentication successful

🔄 Initializing MCP session...
✓ MCP session initialized

📋 Available MCP Tools:
==================================================
🔧 add_numbers
   Description: Add two numbers together
   Parameters: ['a', 'b']

🔧 multiply_numbers  
   Description: Multiply two numbers
   Parameters: ['x', 'y']

🔧 greet_user
   Description: Greet a user by name
   Parameters: ['name']

✅ Successfully connected to MCP server!
Found 3 tools available.
```

## Troubleshooting

### OAuth Issues

#### Common Configuration Problems
- ✅ **Callback URLs**: Ensure `http://localhost:3000` is configured
- ✅ **OAuth Flows**: Verify `authorization_code` is enabled for interactive modes
- ✅ **Scopes**: Check `openid email aws.cognito.signin.user.admin` are allowed
- ✅ **Client Secret**: Required for Mode 3 (M2M), optional for others

#### Mode-Specific Issues

**Mode 1 (Manual)**:
- Check browser console for CORS issues
- Verify callback URL is correctly copied from browser
- Ensure test user exists and password is correct

**Mode 2 (Quick)**:
- Requires `OAUTH_TEST_USERNAME` and `OAUTH_TEST_PASSWORD` in `.env.local`
- Only works with AWS Cognito (not generic OAuth providers)
- User must exist in Cognito User Pool with correct password

**Mode 3 (M2M)**:
- Client secret is mandatory - generate using AWS CLI or console
- Verify `client_credentials` flow is enabled
- May require custom resource server scopes for advanced use cases

**Mode 4 (Native SDK)**:
- Auto-detects authentication mode based on `client_secret` presence
- Handles cross-domain OAuth (Cognito) and MCP (AgentCore) servers automatically
- Uses automatic token refresh for both interactive and M2M modes

### SigV4 Issues

- **Check AWS credentials**: `aws sts get-caller-identity`
- **Verify IAM permissions**: Ensure AgentCore runtime access
- **Region configuration**: Match your AgentCore runtime region
- **ARN format**: Ensure correct format `arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/ID`

### Common Connection Issues

1. **Network connectivity**: Ensure internet access to OAuth provider and AWS
2. **Firewall settings**: Allow outbound HTTPS connections (ports 443, 80)
3. **DNS resolution**: Verify OAuth discovery URL is accessible
4. **Certificate issues**: Ensure system certificates are up to date

## Advanced Configuration

### Custom OAuth 2.0 Providers

The OAuth client supports any OpenID Connect compliant provider:

```bash
# Google
OAUTH_DISCOVERY_URL=https://accounts.google.com/.well-known/openid_configuration
OAUTH_CLIENT_ID=your_google_client_id

# Microsoft Azure AD
OAUTH_DISCOVERY_URL=https://login.microsoftonline.com/{tenant-id}/v2.0/.well-known/openid_configuration
OAUTH_CLIENT_ID=your_azure_client_id

# Auth0
OAUTH_DISCOVERY_URL=https://your-domain.auth0.com/.well-known/openid_configuration
OAUTH_CLIENT_ID=your_auth0_client_id
```

### Dynamic Tool Invocation

Configure automatic tool testing in `.env.local`:

```bash
# Tool to test
MCP_TEST_TOOL_NAME=add_numbers

# Parameters as JSON
MCP_TEST_TOOL_PARAMS={"a": 5, "b": 3}
```

## Related Documentation

- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [Amazon Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/)
- [AWS Cognito OAuth 2.0 Documentation](https://docs.aws.amazon.com/cognito/latest/developerguide/)
- [AWS IAM Authentication](https://docs.aws.amazon.com/IAM/latest/UserGuide/)

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review the MCP client logs for detailed error messages
3. Verify your AWS Cognito/IAM configuration
4. Ensure your AgentCore runtime is running and accessible